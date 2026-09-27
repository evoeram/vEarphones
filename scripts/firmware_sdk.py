#!/usr/bin/env python3
"""
BES2710 VIVO TWS 5i Firmware SDK
================================
Инструмент для распаковки, модификации и перепаковки прошивки vivo TWS 5i.

Формат прошивки:
  [VIVO Header (1024B)] [BES OTA Magic 0xFFFFFFFF] [Chunk]*N [CRC32 Footer]
  
Каждый chunk:
  [size(4, BE)] [LZMA compressed data]
  
Декомпрессированный chunk:
  [VIVDIF01 header (48B)] [partition data / diff blocks]

Использование:
  python firmware_sdk.py unpack  <input.bin>  <output_dir>
  python firmware_sdk.py inspect <input.bin>
  python firmware_sdk.py repack  <input_dir>  <output.bin>
  python firmware_sdk.py patch   <input.bin>  <output.bin> --chunk N --offset 0xXX --bytes "AA BB CC"
  python firmware_sdk.py extract <input.bin>  <chunk_N> <output.bin>
  python firmware_sdk.py replace <input.bin>  <chunk_N> <replacement.bin> <output.bin>
"""

import struct, lzma, os, json, sys, hashlib, argparse


# ─── VIVDIF01 Header (48 bytes) ───────────────────────────────────────────────
VIVDIF_MAGIC = b'VIVDIF01'
VIVDIF_HEADER_SIZE = 48

def parse_vivdif_header(data):
    """Parse VIVDIF01 header from decompressed chunk data."""
    if len(data) < VIVDIF_HEADER_SIZE:
        return None
    magic = data[:8]
    if magic != VIVDIF_MAGIC:
        return {'magic': magic.decode('ascii', errors='replace'), 'valid': False}
    return {
        'magic': 'VIVDIF01',
        'valid': True,
        'part_id':     struct.unpack_from('<Q', data, 8)[0],
        'flash_addr':  struct.unpack_from('<Q', data, 16)[0],
        'part_size':   struct.unpack_from('<Q', data, 24)[0],
        'data_offset': struct.unpack_from('<Q', data, 32)[0],
        'num_blocks':  struct.unpack_from('<Q', data, 40)[0],
    }


# ─── Unpack ───────────────────────────────────────────────────────────────────
def unpack_firmware(input_path, output_dir):
    """Распаковывает прошивку в отдельные chunk файлы."""
    with open(input_path, 'rb') as f:
        data = f.read()
    
    bes_start = data.find(b'\xff\xff\xff\xff')
    if bes_start < 0:
        print("ERROR: BES OTA magic 0xFFFFFFFF not found")
        return False
    
    vivo_header = data[:bes_start]
    print(f"VIVO header: {len(vivo_header)} bytes (0x0000-0x{bes_start-1:04X})")
    
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'vivo_header.bin'), 'wb') as f:
        f.write(vivo_header)
    
    pos = bes_start + 4
    chunks = []
    while pos < len(data) - 20:
        size_be = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if size_be == 0 or size_be > len(data) - pos:
            break
        lzma_data = data[pos:pos+size_be]
        pos += size_be
        
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        decompressed = dec.decompress(lzma_data)
        hdr = parse_vivdif_header(decompressed)
        
        chunk_info = {
            'index': len(chunks),
            'compressed_offset': pos - size_be - 4,
            'compressed_size': size_be,
            'decompressed_size': len(decompressed),
            **hdr,
        }
        chunks.append(chunk_info)
        
        path = os.path.join(output_dir, f"chunk_{len(chunks)-1:02d}.bin")
        with open(path, 'wb') as f:
            f.write(decompressed)
        
        print(f"  Chunk {len(chunks)-1:2d}: partID=0x{hdr['part_id']:03X} addr=0x{hdr['flash_addr']:04X} "
              f"size=0x{hdr['part_size']:04X} blocks={hdr['num_blocks']:3d} "
              f"comp={size_be:5d}B decomp={len(decompressed):6d}B")
    
    # Save metadata
    meta = {
        'input_file': os.path.basename(input_path),
        'input_size': len(data),
        'vivo_header_size': len(vivo_header),
        'bes_ota_start': bes_start,
        'num_chunks': len(chunks),
        'total_decompressed': sum(c['decompressed_size'] for c in chunks),
        'chunks': chunks,
    }
    with open(os.path.join(output_dir, 'metadata.json'), 'w') as f:
        json.dump(meta, f, indent=2)
    
    print(f"\nTotal: {len(chunks)} chunks, {meta['total_decompressed']} bytes decompressed")
    print(f"Saved to: {output_dir}")
    return True


# ─── Inspect ──────────────────────────────────────────────────────────────────
def inspect_firmware(input_path):
    """Показывает структуру прошивки."""
    with open(input_path, 'rb') as f:
        data = f.read()
    
    print(f"File: {input_path}")
    print(f"Size: {len(data)} bytes ({len(data)/1024:.1f} KB)")
    
    bes_start = data.find(b'\xff\xff\xff\xff')
    if bes_start < 0:
        print("ERROR: BES OTA magic not found")
        return
    
    print(f"\n{'─'*70}")
    print(f"VIVO Header: 0x0000-0x{bes_start-1:04X} ({bes_start} bytes)")
    print(f"  Magic: {data[:4]} (reversed: {data[:4][::-1]})")
    
    print(f"\n{'─'*70}")
    print(f"BES OTA Data: 0x{bes_start:04X}")
    print(f"  Magic: 0xFFFFFFFF")
    
    pos = bes_start + 4
    idx = 0
    while pos < len(data) - 20:
        size_be = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if size_be == 0 or size_be > len(data) - pos:
            break
        lzma_data = data[pos:pos+size_be]
        pos += size_be
        
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        decompressed = dec.decompress(lzma_data)
        hdr = parse_vivdif_header(decompressed)
        
        # Find non-zero regions
        nz_count = sum(1 for b in decompressed[VIVDIF_HEADER_SIZE:] if b != 0)
        data_size = len(decompressed) - VIVDIF_HEADER_SIZE
        
        # Find ASCII strings
        strings = []
        current = ''
        for b in decompressed:
            if 32 <= b < 127:
                current += chr(b)
            else:
                if len(current) >= 6:
                    strings.append(current)
                current = ''
        
        print(f"  Chunk {idx:2d}: partID=0x{hdr['part_id']:03X} addr=0x{hdr['flash_addr']:04X} "
              f"size=0x{hdr['part_size']:04X} blocks={hdr['num_blocks']:3d} "
              f"comp={size_be:5d}B decomp={len(decompressed):6d}B nz={nz_count:5d}")
        if strings:
            print(f"           strings: {strings[:5]}")
        idx += 1
    
    crc_pos = data.find(b'CRC32_OF_IMAGE=')
    if crc_pos >= 0:
        print(f"\n{'─'*70}")
        print(f"CRC32 Footer: 0x{crc_pos:04X}")
        print(f"  {data[crc_pos:].decode('ascii', errors='replace').strip()}")


# ─── Repack ───────────────────────────────────────────────────────────────────
def repack_firmware(input_dir, output_path):
    """Перепаковывает chunk файлы обратно в прошивку."""
    header_path = os.path.join(input_dir, 'vivo_header.bin')
    meta_path = os.path.join(input_dir, 'metadata.json')
    
    if not os.path.exists(header_path) or not os.path.exists(meta_path):
        print("ERROR: vivo_header.bin or metadata.json not found in input dir")
        return False
    
    with open(header_path, 'rb') as f:
        vivo_header = f.read()
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    
    result = vivo_header + b'\xff\xff\xff\xff'
    
    for i in range(meta['num_chunks']):
        chunk_path = os.path.join(input_dir, f"chunk_{i:02d}.bin")
        with open(chunk_path, 'rb') as f:
            chunk_data = f.read()
        
        compressor = lzma.LZMACompressor(
            format=lzma.FORMAT_ALONE,
            filters=[{'id': lzma.FILTER_LZMA1, 'preset': 9}]
        )
        compressed = compressor.compress(chunk_data) + compressor.flush()
        
        size_be = struct.pack('>I', len(compressed))
        result += size_be + compressed
        
        print(f"  Chunk {i:2d}: {len(chunk_data)}B → {len(compressed)}B")
    
    result += b'CRC32_OF_IMAGE=0x00000000\n'
    
    with open(output_path, 'wb') as f:
        f.write(result)
    
    print(f"\nOutput: {output_path} ({len(result)} bytes)")
    return True


# ─── Patch ────────────────────────────────────────────────────────────────────
def patch_firmware(input_path, output_path, chunk_idx, offset, new_bytes):
    """Патчит конкретные байты в chunk'е прошивки."""
    with open(input_path, 'rb') as f:
        data = f.read()
    
    bes_start = data.find(b'\xff\xff\xff\xff')
    pos = bes_start + 4
    
    chunks = []
    while pos < len(data) - 20:
        size_be = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if size_be == 0 or size_be > len(data) - pos:
            break
        lzma_data = data[pos:pos+size_be]
        pos += size_be
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        decompressed = dec.decompress(lzma_data)
        chunks.append(decompressed)
    
    if chunk_idx >= len(chunks):
        print(f"ERROR: chunk {chunk_idx} not found (only {len(chunks)} chunks)")
        return False
    
    # Apply patch
    chunk = bytearray(chunks[chunk_idx])
    if offset + len(new_bytes) > len(chunk):
        print(f"ERROR: offset 0x{offset:X} + {len(new_bytes)} bytes exceeds chunk size {len(chunk)}")
        return False
    
    old_bytes = bytes(chunk[offset:offset+len(new_bytes)])
    chunk[offset:offset+len(new_bytes)] = new_bytes
    chunks[chunk_idx] = bytes(chunk)
    
    print(f"Patched chunk {chunk_idx} at offset 0x{offset:X}:")
    print(f"  Old: {old_bytes.hex(' ')}")
    print(f"  New: {new_bytes.hex(' ')}")
    
    # Repack
    result = data[:bes_start] + b'\xff\xff\xff\xff'
    for chunk_data in chunks:
        compressor = lzma.LZMACompressor(
            format=lzma.FORMAT_ALONE,
            filters=[{'id': lzma.FILTER_LZMA1, 'preset': 9}]
        )
        compressed = compressor.compress(chunk_data) + compressor.flush()
        result += struct.pack('>I', len(compressed)) + compressed
    
    result += b'CRC32_OF_IMAGE=0x00000000\n'
    
    with open(output_path, 'wb') as f:
        f.write(result)
    
    print(f"\nOutput: {output_path} ({len(result)} bytes)")
    return True


# ─── Extract / Replace ────────────────────────────────────────────────────────
def extract_chunk(input_path, chunk_idx, output_path):
    """Извлекает один chunk в отдельный файл."""
    with open(input_path, 'rb') as f:
        data = f.read()
    bes_start = data.find(b'\xff\xff\xff\xff')
    pos = bes_start + 4
    idx = 0
    while pos < len(data) - 20:
        size_be = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if size_be == 0 or size_be > len(data) - pos:
            break
        lzma_data = data[pos:pos+size_be]
        pos += size_be
        if idx == chunk_idx:
            dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
            decompressed = dec.decompress(lzma_data)
            with open(output_path, 'wb') as f:
                f.write(decompressed)
            print(f"Extracted chunk {chunk_idx} ({len(decompressed)} bytes) → {output_path}")
            return True
        idx += 1
    print(f"ERROR: chunk {chunk_idx} not found")
    return False


def replace_chunk(input_path, chunk_idx, replacement_path, output_path):
    """Заменяет один chunk на новый."""
    with open(replacement_path, 'rb') as f:
        new_chunk = f.read()
    with open(input_path, 'rb') as f:
        data = f.read()
    
    bes_start = data.find(b'\xff\xff\xff\xff')
    pos = bes_start + 4
    chunks = []
    while pos < len(data) - 20:
        size_be = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if size_be == 0 or size_be > len(data) - pos:
            break
        lzma_data = data[pos:pos+size_be]
        pos += size_be
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        decompressed = dec.decompress(lzma_data)
        chunks.append(decompressed)
    
    if chunk_idx >= len(chunks):
        print(f"ERROR: chunk {chunk_idx} not found")
        return False
    
    old_size = len(chunks[chunk_idx])
    chunks[chunk_idx] = new_chunk
    print(f"Replaced chunk {chunk_idx}: {old_size}B → {len(new_chunk)}B")
    
    result = data[:bes_start] + b'\xff\xff\xff\xff'
    for chunk_data in chunks:
        compressor = lzma.LZMACompressor(
            format=lzma.FORMAT_ALONE,
            filters=[{'id': lzma.FILTER_LZMA1, 'preset': 9}]
        )
        compressed = compressor.compress(chunk_data) + compressor.flush()
        result += struct.pack('>I', len(compressed)) + compressed
    result += b'CRC32_OF_IMAGE=0x00000000\n'
    
    with open(output_path, 'wb') as f:
        f.write(result)
    print(f"Output: {output_path} ({len(result)} bytes)")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='BES2710 VIVO TWS 5i Firmware SDK')
    sub = parser.add_subparsers(dest='command')
    
    p_unpack = sub.add_parser('unpack', help='Распаковать прошивку')
    p_unpack.add_argument('input', help='Input .bin file')
    p_unpack.add_argument('output_dir', help='Output directory')
    
    p_inspect = sub.add_parser('inspect', help='Показать структуру прошивки')
    p_inspect.add_argument('input', help='Input .bin file')
    
    p_repack = sub.add_parser('repack', help='Перепаковать chunks обратно')
    p_repack.add_argument('input_dir', help='Directory with chunks')
    p_repack.add_argument('output', help='Output .bin file')
    
    p_patch = sub.add_parser('patch', help='Патчит байты в chunk')
    p_patch.add_argument('input', help='Input .bin file')
    p_patch.add_argument('output', help='Output .bin file')
    p_patch.add_argument('--chunk', type=int, required=True, help='Chunk index')
    p_patch.add_argument('--offset', type=lambda x: int(x, 0), required=True, help='Offset in chunk (hex or dec)')
    p_patch.add_argument('--bytes', required=True, help='New bytes as hex string "AA BB CC" or "AABBCC"')
    
    p_extract = sub.add_parser('extract', help='Извлечь chunk в файл')
    p_extract.add_argument('input', help='Input .bin file')
    p_extract.add_argument('chunk', type=int, help='Chunk index')
    p_extract.add_argument('output', help='Output file')
    
    p_replace = sub.add_parser('replace', help='Заменить chunk')
    p_replace.add_argument('input', help='Input .bin file')
    p_replace.add_argument('chunk', type=int, help='Chunk index')
    p_replace.add_argument('replacement', help='Replacement .bin file')
    p_replace.add_argument('output', help='Output .bin file')
    
    args = parser.parse_args()
    
    if args.command == 'unpack':
        unpack_firmware(args.input, args.output_dir)
    elif args.command == 'inspect':
        inspect_firmware(args.input)
    elif args.command == 'repack':
        repack_firmware(args.input_dir, args.output)
    elif args.command == 'patch':
        hex_str = args.bytes.replace(' ', '')
        new_bytes = bytes.fromhex(hex_str)
        patch_firmware(args.input, args.output, args.chunk, args.offset, new_bytes)
    elif args.command == 'extract':
        extract_chunk(args.input, args.chunk, args.output)
    elif args.command == 'replace':
        replace_chunk(args.input, args.chunk, args.replacement, args.output)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
