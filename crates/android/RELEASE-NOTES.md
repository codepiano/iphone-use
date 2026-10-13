Android control preview: CLI JSON, authenticated loopback HTTP and stdio MCP.
Read UI elements, tap, long press, swipe, scroll, type into native text fields,
press Back/Home, launch apps and request screenshots. iPhone and Android share
snapshot hashing, semantic element deltas, scroll geometry and progress advice.

Requires Android platform tools and an explicitly authorized device. The pinned
UIAutomator runner is downloaded separately and verified by SHA-256. A narrow,
hash-gated constructor patch restricts it to device loopback; no unauthenticated
LAN control port is opened. No Python,
Appium or root requirement. No on-phone daemon, cloud fleet or live video.

Mutations are never automatically retried. Batches stop at the first failure
and report completed steps; lost acknowledgements are reported as unknown.
Password and WebView text fields are outside this preview's supported text route.
