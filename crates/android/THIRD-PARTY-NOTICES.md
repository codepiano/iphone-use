# Android runner

`android-use setup` downloads the unmodified `u2.jar` 0.4.0 from
[openatx/android-uiautomator-server-jar](https://github.com/openatx/android-uiautomator-server-jar/releases/tag/0.4.0).
The runner is separate from the Rust binary and its SHA-256 is verified before use.
At startup, android-use generates a modified copy that changes NanoHTTPD's default
constructor from a null hostname to the existing 127.0.0.1 constant. The fixed
constructor instructions and alignment padding are checked before patching; DEX
SHA-1 and Adler-32 checksums are regenerated. All following DEX offsets are retained.
This copy listens only on the device loopback address, at port 19008.
See the upstream project for its source and dependency notices.

The MIT License (MIT)
Copyright (c) 2015 xiaocong@gmail.com

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
