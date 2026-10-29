//! One contact with explicit sample times, in the planner's logical viewport.
//! No resampling, scaling to a different screen, entropy, or dispatch lives here.
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

pub const MAX_SAMPLES: usize = 512;
pub const MAX_TOTAL_MS: u64 = 16_000;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Viewport {
    pub width: u32,
    pub height: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Sample {
    pub x: f64,
    pub y: f64,
    pub t_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Path {
    pub viewport: Viewport,
    pub samples: Vec<Sample>,
    #[serde(default)]
    pub hold_before_ms: u64,
    #[serde(default)]
    pub hold_after_ms: u64,
}

impl Path {
    pub fn parse(value: &Value) -> Result<Self, &'static str> {
        let path: Self = serde_json::from_value(value.clone()).map_err(|_| {
            "touch_path needs viewport, samples {x,y,t_ms}, and optional integer holds only"
        })?;
        path.validate()?;
        Ok(path)
    }

    pub fn total_ms(&self) -> u64 {
        self.samples
            .last()
            .map_or(0, |p| p.t_ms)
            .saturating_add(self.hold_before_ms)
            .saturating_add(self.hold_after_ms)
    }

    pub fn validate(&self) -> Result<(), &'static str> {
        if !(2..=100_000).contains(&self.viewport.width)
            || !(2..=100_000).contains(&self.viewport.height)
            || !(2..=MAX_SAMPLES).contains(&self.samples.len())
        {
            return Err("touch_path needs a 2..100000 viewport and 2..512 samples");
        }
        if self.samples[0].t_ms != 0
            || self.samples.windows(2).any(|p| p[1].t_ms <= p[0].t_ms)
            || self.samples.iter().any(|p| {
                !p.x.is_finite()
                    || !p.y.is_finite()
                    || !(0.0..=(self.viewport.width - 1) as f64).contains(&p.x)
                    || !(0.0..=(self.viewport.height - 1) as f64).contains(&p.y)
            })
        {
            return Err("touch_path coordinates must be on screen; sample times start at 0 and strictly increase");
        }
        if self.hold_before_ms > 3000
            || self.hold_after_ms > 3000
            || self.samples.last().unwrap().t_ms > 10_000
            || !(10..=MAX_TOTAL_MS).contains(&self.total_ms())
        {
            return Err("touch_path needs 10..16000 ms total, movement at most 10000 ms and holds at most 3000 ms");
        }
        Ok(())
    }

    pub fn matches_viewport(&self, width: f64, height: f64) -> bool {
        width == self.viewport.width as f64 && height == self.viewport.height as f64
    }

    pub fn actions(&self) -> Result<Value, &'static str> {
        self.validate()?;
        let first = &self.samples[0];
        let mut steps = vec![
            json!({"type":"pointerMove","duration":0,"x":first.x,"y":first.y}),
            json!({"type":"pointerDown","button":0}),
        ];
        if self.hold_before_ms > 0 {
            steps.push(json!({"type":"pause","duration":self.hold_before_ms}));
        }
        for pair in self.samples.windows(2) {
            let duration = pair[1].t_ms - pair[0].t_ms;
            steps.push(if pair[0].x == pair[1].x && pair[0].y == pair[1].y {
                json!({"type":"pause","duration":duration})
            } else {
                json!({"type":"pointerMove","duration":duration,"x":pair[1].x,"y":pair[1].y})
            });
        }
        if self.hold_after_ms > 0 {
            steps.push(json!({"type":"pause","duration":self.hold_after_ms}));
        }
        steps.push(json!({"type":"pointerUp","button":0}));
        Ok(json!(steps))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> Value {
        json!({"viewport":{"width":430,"height":932},"samples":[
            {"x":30.0,"y":80.0,"t_ms":0}, {"x":30.0,"y":80.0,"t_ms":17},
            {"x":31.0,"y":80.0,"t_ms":53}, {"x":31.0,"y":81.0,"t_ms":100}],
            "hold_before_ms":20,"hold_after_ms":30})
    }
    #[test]
    fn preserves_nonuniform_time_and_stationary_contact() {
        let path = Path::parse(&fixture()).unwrap();
        let actions = path.actions().unwrap();
        let actions = actions.as_array().unwrap();
        assert_eq!(actions[2], json!({"type":"pause","duration":20}));
        assert_eq!(actions[3], json!({"type":"pause","duration":17}));
        assert_eq!(actions[4]["duration"], 36);
        assert_eq!(actions[5]["duration"], 47);
        assert_eq!(
            actions
                .iter()
                .filter(|s| s["type"] == "pointerDown")
                .count(),
            1
        );
        assert_eq!(
            actions.iter().filter(|s| s["type"] == "pointerUp").count(),
            1
        );
        assert_eq!(
            actions
                .iter()
                .filter_map(|s| s["duration"].as_u64())
                .sum::<u64>(),
            150
        );
        assert!(path.matches_viewport(430.0, 932.0));
        assert!(!path.matches_viewport(932.0, 430.0));
    }
    #[test]
    fn rejects_invalid_paths_before_export() {
        for (pointer, value) in [
            ("/samples/0/t_ms", json!(1)),
            ("/samples/2/t_ms", json!(17)),
            ("/samples/1/x", json!(430)),
            ("/samples/1/y", json!(-1)),
            ("/samples/3/t_ms", json!(u64::MAX)),
            ("/hold_before_ms", json!(true)),
            ("/hold_after_ms", json!(3001)),
            ("/viewport/width", json!(1)),
            ("/samples", json!([])),
        ] {
            let mut value0 = fixture();
            *value0.pointer_mut(pointer).unwrap() = value;
            assert!(Path::parse(&value0).is_err(), "{value0}");
        }
        let mut value = fixture();
        value["samples"][0]["pressure"] = json!(1);
        assert!(Path::parse(&value).is_err());
    }

    #[test]
    fn retains_dense_paths_and_rejects_sample_overflow() {
        let mut value = fixture();
        value["samples"] = json!((0..MAX_SAMPLES)
            .map(|t| json!({
                "x":30.0,"y":80.0,"t_ms":t
            }))
            .collect::<Vec<_>>());
        let path = Path::parse(&value).unwrap();
        assert_eq!(
            path.actions().unwrap().as_array().unwrap().len(),
            MAX_SAMPLES + 4
        );
        value["samples"]
            .as_array_mut()
            .unwrap()
            .push(json!({"x":30,"y":80,"t_ms":MAX_SAMPLES}));
        assert!(Path::parse(&value).is_err());
    }
}
