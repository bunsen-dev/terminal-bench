#!/bin/bash
set -eux

apt-get update -y
apt-get install -y \
  bc \
  bison \
  build-essential \
  cpio \
  expect \
  flex \
  libelf-dev \
  libncurses-dev \
  libssl-dev \
  python3 \
  python3-pip \
  qemu-system \
  wget
pip3 install --break-system-packages pytest

mkdir -p /seed/linux-6.9/arch/x86/boot /seed/linux-6.9/usr /seed/ramfs
cd /app

wget https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.9.tar.xz
tar xf linux-6.9.tar.xz

sed -i '/boot_cpu_hotplug_init();/a printk(KERN_INFO "Hello, this is a custom kernel");' linux-6.9/init/main.c

cd /app/linux-6.9
make defconfig
./scripts/config --enable TTY
./scripts/config --enable SERIAL_8250
./scripts/config --enable SERIAL_8250_CONSOLE
./scripts/config --enable PRINTK
./scripts/config --enable BLK_DEV_INITRD
make olddefconfig

# Build only the immutable boot artifacts the task needs.
make -j"$(nproc)" bzImage
make -j"$(nproc)" usr/gen_init_cpio

cp arch/x86/boot/bzImage /seed/linux-6.9/arch/x86/boot/bzImage
cp usr/gen_init_cpio /seed/linux-6.9/usr/gen_init_cpio

cat > /seed/ramfs/basic-init <<'EOF'
#!/bin/busybox sh

busybox mkdir -p /dev /etc /proc /root /sbin /sys /usr/bin /usr/sbin
busybox mount -t proc proc /proc
busybox mount -t sysfs sys /sys
busybox mount -t devtmpfs dev /dev
echo Starting up...
echo ttyS0::respawn:/sbin/getty -L ttyS0 115200 vt100 >> /etc/inittab
echo Login with root and no password. > /etc/issue
echo >> /etc/issue
echo root::0:0:root:/root:/bin/sh > /etc/passwd
busybox mdev -s
busybox --install
hostname localhost
ip link set lo up
echo 5 > /proc/sys/kernel/printk
exec /linuxrc
EOF
chmod +x /seed/ramfs/basic-init

wget -O /seed/ramfs/busybox-x86_64 https://busybox.net/downloads/binaries/1.31.0-defconfig-multiarch-musl/busybox-x86_64
chmod +x /seed/ramfs/busybox-x86_64

rm -rf /app/linux-6.9 /app/linux-6.9.tar.xz
rm -rf /var/lib/apt/lists/*
