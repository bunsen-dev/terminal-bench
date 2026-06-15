from pathlib import Path
import subprocess

EXPECT_SCRIPT = r"""
#!/usr/bin/expect -f

set timeout 60
log_user 1

spawn qemu-system-x86_64 -kernel /workspace/linux-6.9/arch/x86/boot/bzImage -initrd /workspace/ramfs/initramfs.cpio.gz -append "console=ttyS0" -nographic

expect "localhost login: "
send "root\r"

expect "# "
send "dmesg | grep -F \"Hello, this is a custom kernel\"\r"
expect "Hello, this is a custom kernel"
expect "# "
send "poweroff\r"
"""


def _assert_expected_source_edit() -> None:
    source_text = Path("/workspace/linux-6.9/init/main.c").read_text()
    signature_index = source_text.find("start_kernel(void)")
    assert signature_index != -1, "Could not find start_kernel(void) in init/main.c"

    body_start = source_text.find("{", signature_index)
    assert body_start != -1, "Could not find the start_kernel function body"

    depth = 0
    body_end = None
    for index in range(body_start, len(source_text)):
        char = source_text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                body_end = index
                break

    assert body_end is not None, "Could not determine the end of start_kernel"

    start_kernel_body = source_text[body_start:body_end]
    expected_line = 'printk(KERN_INFO "Hello, this is a custom kernel");'
    assert expected_line in start_kernel_body, (
        "Expected the custom printk line inside start_kernel in "
        "/workspace/linux-6.9/init/main.c"
    )


def _assert_expected_outputs_exist() -> None:
    expected_paths = [
        Path("/workspace/linux-6.9/arch/x86/boot/bzImage"),
        Path("/workspace/linux-6.9/usr/gen_init_cpio"),
        Path("/workspace/ramfs/initramfs.cpio.gz"),
    ]
    for expected_path in expected_paths:
        assert expected_path.exists(), f"Missing expected output: {expected_path}"


def test_expect() -> None:
    """Verify the built kernel and initramfs boot and expose the custom printk."""

    _assert_expected_source_edit()
    _assert_expected_outputs_exist()

    exp_path = Path("a.exp")
    exp_path.write_text(EXPECT_SCRIPT)

    result = subprocess.run(
        ["expect", "-f", str(exp_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )

    combined_output = result.stdout + result.stderr
    expected_output = "Hello, this is a custom kernel"

    assert result.returncode == 0, (
        "QEMU boot verification failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert expected_output in combined_output, (
        "Expected the custom printk to appear in guest output.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
