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
  genisoimage \
  libelf-dev \
  libncurses-dev \
  libssl-dev \
  python3 \
  python3-pip \
  qemu-system \
  wget
pip3 install --break-system-packages pytest

mkdir -p /seed/linux-6.9/arch/x86/boot /seed/ramfs
cd /app

wget https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.9.tar.xz
tar xf linux-6.9.tar.xz

cd /app/linux-6.9
make defconfig
./scripts/config --enable TTY
./scripts/config --enable SERIAL_8250
./scripts/config --enable SERIAL_8250_CONSOLE
./scripts/config --enable PRINTK
./scripts/config --enable BLK_DEV_INITRD
make olddefconfig

# Build only the bootable kernel image and cpio helper needed to seed the task.
make -j"$(nproc)" bzImage
make -j"$(nproc)" usr/gen_init_cpio
cp arch/x86/boot/bzImage /seed/linux-6.9/arch/x86/boot/bzImage

mkdir /app/ramfs
cd /app/ramfs

cat > basic-init << 'EOF'
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

chmod +x basic-init

wget -O busybox-x86_64 https://busybox.net/downloads/binaries/1.31.0-defconfig-multiarch-musl/busybox-x86_64
chmod +x busybox-x86_64

# Seed a small glibc runtime so a normal Ubuntu-built `tcc` binary can run
# inside the otherwise tiny BusyBox guest after the ISO contents are copied in.
mkdir -p runtime-root/lib/x86_64-linux-gnu runtime-root/lib64

loader_src="$(readlink -f /lib64/ld-linux-x86-64.so.2)"
install -Dm755 "$loader_src" runtime-root/lib64/ld-linux-x86-64.so.2
install -Dm755 "$loader_src" runtime-root/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2

for lib in \
  libc.so.6 \
  libdl.so.2 \
  libgcc_s.so.1 \
  libm.so.6 \
  libpthread.so.0 \
  librt.so.1
do
  install -Dm644 "/lib/x86_64-linux-gnu/${lib}" "runtime-root/lib/x86_64-linux-gnu/${lib}"
done

cat > initramfs.list << 'EOF'
# Simple busybox based initramfs

dir /dev 0755 0 0
nod /dev/console 0600 0 0 c 5 1
dir /root 0700 0 0
dir /bin 0755 0 0
dir /sbin 0755 0 0
dir /lib 0755 0 0
dir /lib64 0755 0 0
dir /lib/x86_64-linux-gnu 0755 0 0
file /init basic-init 0755 0 0
file /bin/busybox busybox-x86_64 0755 0 0
file /lib64/ld-linux-x86-64.so.2 runtime-root/lib64/ld-linux-x86-64.so.2 0755 0 0
file /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 runtime-root/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 0755 0 0
file /lib/x86_64-linux-gnu/libc.so.6 runtime-root/lib/x86_64-linux-gnu/libc.so.6 0644 0 0
file /lib/x86_64-linux-gnu/libdl.so.2 runtime-root/lib/x86_64-linux-gnu/libdl.so.2 0644 0 0
file /lib/x86_64-linux-gnu/libgcc_s.so.1 runtime-root/lib/x86_64-linux-gnu/libgcc_s.so.1 0644 0 0
file /lib/x86_64-linux-gnu/libm.so.6 runtime-root/lib/x86_64-linux-gnu/libm.so.6 0644 0 0
file /lib/x86_64-linux-gnu/libpthread.so.0 runtime-root/lib/x86_64-linux-gnu/libpthread.so.0 0644 0 0
file /lib/x86_64-linux-gnu/librt.so.1 runtime-root/lib/x86_64-linux-gnu/librt.so.1 0644 0 0
EOF

/app/linux-6.9/usr/gen_init_cpio initramfs.list > /seed/ramfs/initramfs.cpio
gzip -9 /seed/ramfs/initramfs.cpio

cd ..

wget https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27.tar.bz2
tar xf tcc-0.9.27.tar.bz2
mv /app/tcc-0.9.27 /seed/tcc-0.9.27

rm -rf /app/linux-6.9 /app/linux-6.9.tar.xz /app/ramfs /app/tcc-0.9.27.tar.bz2
rm -rf /var/lib/apt/lists/*
