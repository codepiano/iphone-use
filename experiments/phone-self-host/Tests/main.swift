import Foundation

func frame(_ object: Any) throws -> Data {
    let body = try JSONSerialization.data(withJSONObject: object)
    return Data("RPPairing".utf8) + Data([UInt8(body.count >> 8), UInt8(body.count & 255)]) + body
}
let fixture: [String: Any] = [
    "originatedBy": "device", "sequenceNumber": 0,
    "message": ["plain": ["_0": ["response": ["_1": ["handshake": ["_0": [
        "wireProtocolVersion": 19, "private_key": "synthetic-secret", "deviceIdentifier": "synthetic-id"
    ]]]]]]]
]
let response = try frame(fixture)
for split in 0..<response.count {
    let partial = try RemotePairingHandshake.response(Data(response.prefix(split)))
    precondition(partial == nil)
}
let summary = try RemotePairingHandshake.response(response)!
precondition(summary.contains("protocol 19"))
precondition(!summary.contains("synthetic-secret") && !summary.contains("synthetic-id"))
for invalid in [Data("NotPairing".utf8) + Data([0, 0]),
                Data("RPPairing".utf8) + Data([0, 0]), try frame(["originatedBy": "host"])] {
    do { _ = try RemotePairingHandshake.response(invalid); fatalError("Accepted malformed response") }
    catch {}
}
let request = try RemotePairingHandshake.request()
let json = try JSONSerialization.jsonObject(with: request.dropFirst(11)) as! [String: Any]
precondition(json["originatedBy"] as? String == "host")
precondition(!String(data: request.dropFirst(11), encoding: .utf8)!.contains("pairSetup"))
print("PASS: fragmented frames, invalid peers, output redaction, handshake-only request")
