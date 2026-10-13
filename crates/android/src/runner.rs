//! Narrow, hash-gated hardening of the pinned upstream runner. NanoHTTPD's
//! one-argument constructor uses a null hostname (all interfaces). Change
//! only that constructor to pass the existing "127.0.0.1" string constant.
//! The extra instruction consumes its two-byte alignment padding; all other
//! DEX offsets remain unchanged. No Python/JDK is required at runtime.
use phone_control::Failure;
use sha1::Sha1;
use sha2::{Digest, Sha256};
use std::io::{Cursor, Read, Write};

const CODE: usize = 2_349_388;
const ORIGINAL: [u8; 12] = [
    0x12, 0x00, 0x70, 0x30, 0x7f, 0x69, 0x01, 0x02, 0x0e, 0x00, 0x00, 0x00,
];
const LOOPBACK: [u8; 12] = [
    0x1a, 0x00, 0x73, 0x17, 0x70, 0x30, 0x7f, 0x69, 0x01, 0x02, 0x0e, 0x00,
];

fn patch_dex(bytes: &mut [u8]) -> Result<(), Failure> {
    let invalid = || {
        Failure::not_sent(
            "runner_patch_mismatch",
            "Pinned runner constructor does not match the loopback patch; nothing started",
        )
    };
    let Some(header) = bytes.get(CODE..CODE + 16) else {
        return Err(invalid());
    };
    // registers=3, incoming=2, outgoing=3, no exception handlers,
    // debug_info_off=3791639, original instructions_size=5.
    if header != [3, 0, 2, 0, 3, 0, 0, 0, 0x17, 0xdb, 0x39, 0, 5, 0, 0, 0]
        || bytes.get(CODE + 16..CODE + 28) != Some(ORIGINAL.as_slice())
    {
        return Err(invalid());
    }
    bytes[CODE + 12..CODE + 16].copy_from_slice(&6u32.to_le_bytes());
    bytes[CODE + 16..CODE + 28].copy_from_slice(&LOOPBACK);
    let signature = Sha1::digest(&bytes[32..]);
    bytes[12..32].copy_from_slice(&signature);
    let checksum = adler2::adler32_slice(&bytes[12..]);
    bytes[8..12].copy_from_slice(&checksum.to_le_bytes());
    Ok(())
}

pub fn harden(original: &[u8]) -> Result<Vec<u8>, Failure> {
    if format!("{:x}", Sha256::digest(original)) != crate::backend::RUNNER_SHA256 {
        return Err(Failure::not_sent(
            "runner_checksum_mismatch",
            "Only the pinned upstream 0.4.0 runner is supported; use android-use setup",
        ));
    }
    let invalid = || {
        Failure::not_sent(
            "runner_archive_failed",
            "Unable to prepare the loopback-only device runner",
        )
    };
    let mut archive = zip::ZipArchive::new(Cursor::new(original)).map_err(|_| invalid())?;
    let mut writer = zip::ZipWriter::new(Cursor::new(Vec::new()));
    let mut patched = false;
    for index in 0..archive.len() {
        let mut entry = archive.by_index(index).map_err(|_| invalid())?;
        let options = zip::write::FileOptions::default()
            .compression_method(entry.compression())
            .last_modified_time(entry.last_modified());
        if entry.is_dir() {
            writer
                .add_directory(entry.name(), options)
                .map_err(|_| invalid())?;
            continue;
        }
        let mut data = Vec::new();
        entry.read_to_end(&mut data).map_err(|_| invalid())?;
        if entry.name() == "classes.dex" {
            patch_dex(&mut data)?;
            patched = true;
        }
        writer
            .start_file(entry.name(), options)
            .map_err(|_| invalid())?;
        writer.write_all(&data).map_err(|_| invalid())?;
    }
    if !patched {
        return Err(invalid());
    }
    Ok(writer.finish().map_err(|_| invalid())?.into_inner())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn constructor_uses_loopback_string_and_keeps_all_following_offsets() {
        let mut bytes = vec![0; CODE + 64];
        bytes[CODE..CODE + 16]
            .copy_from_slice(&[3, 0, 2, 0, 3, 0, 0, 0, 0x17, 0xdb, 0x39, 0, 5, 0, 0, 0]);
        bytes[CODE + 16..CODE + 28].copy_from_slice(&ORIGINAL);
        bytes[CODE + 28..].fill(0x55);
        let tail = bytes[CODE + 28..].to_vec();
        let length = bytes.len();
        patch_dex(&mut bytes).unwrap();
        assert_eq!(&bytes[CODE + 16..CODE + 28], &LOOPBACK);
        assert_eq!(bytes.len(), length);
        assert_eq!(bytes[CODE + 28..], tail);
        assert_eq!(&bytes[12..32], Sha1::digest(&bytes[32..]).as_slice());
        assert_eq!(
            u32::from_le_bytes(bytes[8..12].try_into().unwrap()),
            adler2::adler32_slice(&bytes[12..])
        );
    }
    #[test]
    fn wrong_version_and_wrong_instruction_bytes_fail_closed() {
        assert_eq!(
            harden(b"different runner").unwrap_err().error,
            "runner_checksum_mismatch"
        );
        assert_eq!(
            patch_dex(&mut vec![0; CODE + 64]).unwrap_err().error,
            "runner_patch_mismatch"
        );
    }
}
