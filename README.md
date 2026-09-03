# MiniOS

A custom, bare metal, operating system built from scratch as a learning project.  
Built with hopes and dreams.
Heavily in progress.

## Features

- **Bootloader**: Custom x86 bootloader written in assembly (20-sector loading)
- **Protected Mode**: Full 32-bit protected mode operation
- **GDT**: Global Descriptor Table implementation
- **IDT**: Complete Interrupt Descriptor Table with ISRs
- **PIC**: Programmable Interrupt Controller with remapping
- **Keyboard Driver**: PS/2 keyboard input with scancode-to-ASCII conversion
- **VGA Text Mode**: Text output with scrolling support

## Project Structure

```
├── boot.asm           # Bootloader (first stage)
├── kernel_entry.asm   # Kernel entry point (assembly)
├── kernel.cpp         # Main kernel (C++)
├── idt.asm / idt.cpp  # Interrupt Descriptor Table
├── isr.asm / isr.cpp  # Interrupt Service Routines
├── pic.asm / pic.cpp  # PIC controller
├── ports.cpp          # I/O port operations
├── disk.asm           # Disk reading routines
└── linker.ld          # Linker script (if applicable)
```

## Building

### Prerequisites

- NASM assembler
- i686-elf cross-compiler toolchain
- QEMU for testing 

### Build Commands

```bash
# Assemble bootloader
nasm -f bin boot.asm -o boot.bin

# Compile and link kernel components
# (adjust based on your actual build process)
i686-elf-as kernel_entry.asm -o kernel_entry.o
i686-elf-g++ -ffreestanding -m32 -c kernel.cpp -o kernel.o
# ... additional components ...

# Link everything
i686-elf-ld -o full_kernel.bin -Ttext 0x1000 kernel_entry.o kernel.o ...

# Create OS image
cat boot.bin full_kernel.bin > OS.bin
```

### Running

```bash
qemu-system-i386 -fda OS.bin
```

## Development Environment

- WSL (Ubuntu, Debian derivative) on Windows
- Cross-compilation with i686-elf-gcc toolchain
- QEMU emulator for testing

## Roadmap

- [ ] Timer (IRQ0) implementation
- [ ] Command shell interface
- [ ] Memory management (physical & virtual)
- [ ] File system support

## Resources

Built following various OS development tutorials and resources, including the OSDev Wiki and heavily jumpstarted by 
"Daedalus Community"s OS Dev guide.  Lots of google and reddit posts too.

## License

This project is for educational purposes.
