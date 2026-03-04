// =============================================================================
// 名称: 原子文件写入（Atomic Write via tmp → rename）
// 用途: 写入文件时防止部分写入污染——先写临时文件，完成后原子重命名
// 依赖: stdlib only (std::fs, std::io, std::thread, std::process)
// 适用场景: 任何需要"写入失败不留脏文件"保证的场景：日志轮转、缓存落盘、配置更新
// 来源: https://github.com/Aditya-1304/mapreduce
// 日期: 2026-03-04
// =============================================================================
//
// 原理：POSIX/Windows 均保证 rename() 是原子操作。
// 即使进程在写入过程中崩溃，目标路径要么是旧内容，要么是新内容，不可能是"半写"状态。
// tmp 文件名带 pid + thread_id，多线程/多进程并发写入同一目标文件也安全。

use std::fs::{self, File};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::thread;

// -----------------------------------------------------------------------------
// 生成临时文件路径（pid + thread_id 防冲突）
// -----------------------------------------------------------------------------
fn temp_path(final_path: &Path) -> PathBuf {
    let pid = std::process::id();
    let tid = format!("{:?}", thread::current().id());
    // 例：/tmp/output.txt.tmp-12345-ThreadId(1)
    PathBuf::from(format!("{}.tmp-{}-{}", final_path.display(), pid, tid))
}

// -----------------------------------------------------------------------------
// 原子写入：将 data 写到 final_path，失败时 final_path 保持原状
// -----------------------------------------------------------------------------
fn atomic_write(final_path: &Path, data: &[u8]) -> Result<(), String> {
    let tmp = temp_path(final_path);

    // 1. 写入临时文件
    let file = File::create(&tmp)
        .map_err(|e| format!("failed to create tmp file {}: {}", tmp.display(), e))?;
    let mut writer = BufWriter::new(file);
    writer.write_all(data)
        .map_err(|e| format!("failed to write tmp file: {}", e))?;
    writer.flush()
        .map_err(|e| format!("failed to flush tmp file: {}", e))?;

    // 2. 原子重命名：此后 final_path 要么是新内容，要么是旧内容
    fs::rename(&tmp, final_path)
        .map_err(|e| format!("atomic rename {} -> {} failed: {}", tmp.display(), final_path.display(), e))?;

    Ok(())
}

// -----------------------------------------------------------------------------
// 带自定义 writer 的原子写入（适合写大文件 / 流式写入）
// -----------------------------------------------------------------------------
fn atomic_write_with<F>(final_path: &Path, write_fn: F) -> Result<(), String>
where
    F: FnOnce(&mut BufWriter<File>) -> Result<(), String>,
{
    let tmp = temp_path(final_path);

    let file = File::create(&tmp)
        .map_err(|e| format!("create tmp: {}", e))?;
    let mut writer = BufWriter::new(file);

    // 如果 write_fn 失败，tmp 文件残留但 final_path 不受影响
    write_fn(&mut writer)?;

    writer.flush().map_err(|e| format!("flush: {}", e))?;

    fs::rename(&tmp, final_path)
        .map_err(|e| format!("rename: {}", e))?;

    Ok(())
}

fn main() {
    let path = Path::new("/tmp/atomic-test.txt");

    // 简单用法
    atomic_write(path, b"hello, atomic world\n").unwrap();
    println!("written: {}", fs::read_to_string(path).unwrap().trim());

    // 流式写入用法
    atomic_write_with(path, |w| {
        for i in 0..5 {
            writeln!(w, "line {}", i).map_err(|e| e.to_string())?;
        }
        Ok(())
    }).unwrap();
    println!("written:\n{}", fs::read_to_string(path).unwrap());

    // 清理
    let _ = fs::remove_file(path);
}
