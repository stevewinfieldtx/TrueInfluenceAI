"""Debug subtitle download for a single video"""
import subprocess, os, tempfile

vid = '8jjnEBdiLYI'  # One of Sunny's videos
tmp_dir = tempfile.mkdtemp()
out = os.path.join(tmp_dir, '%(id)s')

cmd = [
    'yt-dlp',
    '--skip-download',
    '--write-auto-sub',
    '--write-sub',
    '--sub-lang', 'en',
    '--sub-format', 'json3',
    '--verbose',
    '-o', out,
    f'https://www.youtube.com/watch?v={vid}'
]

print(f"Running: {' '.join(cmd)}")
print(f"Temp dir: {tmp_dir}\n")

result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

print("=== STDOUT ===")
print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
print("\n=== STDERR ===")
print(result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr)

print(f"\n=== FILES IN TEMP ===")
for f in os.listdir(tmp_dir):
    fpath = os.path.join(tmp_dir, f)
    print(f"  {f}  ({os.path.getsize(fpath)} bytes)")

if not os.listdir(tmp_dir):
    print("  (empty - no files downloaded)")
