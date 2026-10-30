//! Opt-in live-page binding for planned contacts. The baseline is a daemon
//! read, never client-supplied rows; the caller still re-reads before dispatch.
use crate::runner::ElementRow;
use core::touch_path::Path;
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Context {
    pub application: String,
    pub present: Vec<String>,
    #[serde(default)]
    pub absent: Vec<String>,
}

impl Context {
    pub fn parse(value: &Value) -> Result<Self, &'static str> {
        let context: Self = serde_json::from_value(value.clone())
            .map_err(|_| "context needs application, present and optional absent labels only")?;
        let bounded = |s: &String| !s.is_empty() && s.len() <= 512;
        if !bounded(&context.application)
            || context.present.is_empty()
            || context.present.len() + context.absent.len() > 32
            || !context.present.iter().chain(&context.absent).all(bounded)
        {
            return Err("context needs an application and 1..32 bounded exact page anchors");
        }
        Ok(context)
    }

    fn matches(&self, rows: &[ElementRow]) -> bool {
        rows.first().is_some_and(|r| r.kind == "Application" && r.label == self.application)
            && self.present.iter().all(|s| has_anchor(rows, s))
            && self.absent.iter().all(|s| !has_anchor(rows, s))
    }
}

fn has_anchor(rows: &[ElementRow], text: &str) -> bool {
    rows.iter().any(|r| r.visible != Some(false)
        && (r.label == text || r.value.as_deref() == Some(text)))
}

// Same conservative challenge/empty-result policy as the guarded controller.
// Recheck globally: a new warning outside the contact corridor is still a stop.
fn blocker(rows: &[ElementRow]) -> bool {
    const WORDS: &[&str] = &["操作过于频繁", "访问过于频繁", "请求过于频繁", "安全验证",
        "请完成验证", "请输入验证码", "拖动滑块", "异常访问", "验证码", "captcha",
        "too many requests", "verify you are human", "unusual activity",
        "暂无搜索结果", "无搜索结果", "没有找到相关结果", "no results found"];
    rows.iter().filter(|r| r.visible != Some(false)).any(|r| {
        let text = format!("{} {}", r.label, r.value.as_deref().unwrap_or("")).to_lowercase();
        matches!(r.kind.as_str(), "Alert" | "Sheet" | "Dialog")
            || WORDS.iter().any(|word| text.contains(word))
    })
}

fn same_identity(a: &ElementRow, b: &ElementRow) -> bool {
    a.kind == b.kind && a.label == b.label && a.identifier == b.identifier
}

fn in_corridor(row: &ElementRow, path: &Path) -> bool {
    let [x, y, w, h] = row.rect;
    // A small margin also catches controls just beside the sampled path.
    path.samples.windows(2).any(|p| p[0].x.min(p[1].x) <= x + w + 2.0
        && p[0].x.max(p[1].x) >= x - 2.0
        && p[0].y.min(p[1].y) <= y + h + 2.0
        && p[0].y.max(p[1].y) >= y - 2.0)
}

/// Resolve only the original unique semantic target, retaining its exact frame
/// and state. Index shifts from unrelated rows are allowed; retargeting is not.
/// Unbound gestures require an unchanged contact corridor instead.
pub fn verify(
    context: &Context,
    baseline: &[ElementRow],
    current: &[ElementRow],
    element: Option<usize>,
    path: &Path,
) -> Result<Option<usize>, &'static str> {
    if !context.matches(baseline) || !context.matches(current)
        || baseline.first() != current.first()
    {
        return Err("touch_context_changed");
    }
    if blocker(baseline) || blocker(current) {
        return Err("touch_context_blocked");
    }
    let relevant = |r: &&ElementRow| r.visible != Some(false)
        && (context.present.iter().any(|s| r.label == *s || r.value.as_ref() == Some(s))
            || in_corridor(r, path));
    let before: Vec<_> = baseline.iter().filter(relevant).collect();
    let after: Vec<_> = current.iter().filter(relevant).collect();
    if before != after {
        return Err("touch_context_changed");
    }
    let Some(index) = element else { return Ok(None); };
    let target = baseline.get(index).ok_or("touch_target_changed")?;
    if (target.label.is_empty() && target.identifier.as_deref().unwrap_or("").is_empty())
        || baseline.iter().filter(|r| same_identity(r, target)).count() != 1
    {
        return Err("touch_target_changed");
    }
    let matches: Vec<_> = current.iter().enumerate()
        .filter(|(_, r)| same_identity(r, target)).collect();
    match matches.as_slice() {
        [(index, row)] if *row == target => Ok(Some(*index)),
        _ => Err("touch_target_changed"),
    }
}
