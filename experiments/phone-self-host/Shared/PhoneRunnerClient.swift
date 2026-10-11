import Foundation

struct PhoneRunnerClient {
    let expectedBundle: String = Bundle.main.bundleIdentifier ?? ""
    struct Failure: Error {
        let code: String
        var httpStatus: Int? = nil
        var serverError: String? = nil
        var authReason: String? = nil
    }
    func request(_ method: String, _ target: String, body: [String: Any]? = nil) async throws -> [String: Any] {
        guard let saved = ProtectedStore.read("runner_token"), let token = String(data: saved, encoding: .utf8) else { throw Failure(code: "credential_missing") }
        let bytes = try body.map { try JSONSerialization.data(withJSONObject: $0, options: [.sortedKeys]) } ?? Data()
        var request = URLRequest(url: URL(string: "http://127.0.0.1:18100" + target)!)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.httpMethod = method
        request.timeoutInterval = 20
        if method != "GET" { request.httpBody = bytes; request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        let nonce = UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
        request.setValue(RunnerSigning.authorization(token: token, method: method, target: target,
            timestamp: Int64(Date().timeIntervalSince1970), nonce: nonce, body: bytes), forHTTPHeaderField: "Authorization")
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw Failure(code: "runner_request_failed") }
        if http.statusCode != 200 {
            let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            let value = object?["value"] as? [String: Any]
            let reasons = ["bad signature": "bad_signature", "request already seen": "replay",
                "authorization required": "missing", "malformed authorization": "malformed",
                "request timestamp too far from the phone's clock": "clock_skew",
                "this runner was started without IPU_RUNNER_TOKEN; restart it with iphone-use setup": "not_configured"]
            let reason = (value?["message"] as? String).flatMap { reasons[$0] }
            throw Failure(code: "runner_request_failed", httpStatus: http.statusCode, serverError: value?["error"] as? String, authReason: reason)
        }
        guard data.count <= 8_388_608, let value = (try JSONSerialization.jsonObject(with: data)) as? [String: Any] else { throw Failure(code: "invalid_runner_response") }
        return value
    }
    func ownedSource() async throws -> [String: Any] {
        let app = try await request("GET", "/apps/active")
        guard let active = app["value"] as? [String: Any], active["bundleId"] as? String == expectedBundle else { throw Failure(code: "validation_app_not_foreground") }
        let response = try await request("GET", "/source?format=json")
        if let tree = response["value"] as? [String: Any] { return tree }
        if let text = response["value"] as? String,
           let tree = (try JSONSerialization.jsonObject(with: Data(text.utf8))) as? [String: Any] { return tree }
        throw Failure(code: "source_unavailable")
    }
    static func node(_ identifier: String, in tree: [String: Any]) -> [String: Any]? {
        if tree["rawIdentifier"] as? String == identifier || tree["name"] as? String == identifier { return tree }
        for child in tree["children"] as? [[String: Any]] ?? [] {
            if let result = node(identifier, in: child) { return result }
        }
        return nil
    }
    func tap(_ identifier: String) async throws {
        let tree = try await ownedSource()
        guard let node = Self.node(identifier, in: tree), let rect = node["rect"] as? [String: Any],
              let x = rect["x"] as? Double, let y = rect["y"] as? Double,
              let width = rect["width"] as? Double, let height = rect["height"] as? Double,
              width > 0, height > 0 else { throw Failure(code: "validation_target_missing") }
        _ = try await request("POST", "/tap", body: ["x": x + width/2, "y": y + height/2])
    }
}
