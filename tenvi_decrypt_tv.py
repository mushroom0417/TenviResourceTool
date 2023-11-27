 #  -*- coding: utf-8 -*-
import os
import zlib
import argparse
import sys
import json

# python3 tenvi_decrypt_tv.py --cmd unpack --input_dir ***/data --output_dir ***/test_out

input_dir = ""
output_dir = ""
only_debug = False
TV_FILE_VERSION = 258

def decryptXMLInMemory(byteArray):
    counter = 0
    andArray = [0xFB, 0x4F, 0xC1, 0x2F]
    for byte in byteArray:
        highByte = byte & 0xF0
        lowByte = byte & 0x0F
        lowByte = lowByte << 4
        highByte = highByte >> 4
        byte = highByte ^ lowByte
        byteArray[counter] = byte ^ andArray[counter % 4]
        counter = counter + 1
    return byteArray

def encryptXMLInMemory(byteArray):
    counter = 0
    andArray = [0xFB, 0x4F, 0xC1, 0x2F]
    for byte in byteArray:
        byte = byte ^ andArray[counter % 4]
        tempHighByte = byte & 0xF0
        tempLowByte = byte & 0x0F
        lowByte = tempHighByte >> 4
        highByte = tempLowByte << 4
        byte = lowByte ^ highByte
        byteArray[counter] = byte
        counter = counter + 1
    return byteArray

def readInt(currentIndex, buffer, byteNum, moveIndex=False):
    bytes = []
    for i in range(0, byteNum):
        bytes.append(buffer[currentIndex + i])
    num = int.from_bytes(bytes, "little")
    if moveIndex == True:
        currentIndex = currentIndex + byteNum
        return num, currentIndex
    else:
        return num

def writeInt(currentIndex, buffer, byteNum, num):
    bytes = int.to_bytes(num, byteNum, "little")
    for i in range(0, byteNum):
        buffer[currentIndex + i] = bytes[i]
    currentIndex = currentIndex + byteNum
    return currentIndex

def readString(currentIndex, buffer):
    stringLength = readInt(currentIndex, buffer, 2) + 1
    currentIndex = currentIndex + 2
    string = buffer[currentIndex : currentIndex + stringLength - 1].decode("utf-8")
    currentIndex = currentIndex + stringLength
    return string, currentIndex

def writeString(fd, string):
    stringLength = len(string)
    fd.write(int.to_bytes(stringLength, 2, "little"))
    fd.write(string.encode("utf-8"))
    fd.write(b'\x00')

def repackDataTvFile(dataFileName, entries):
    file = open(os.path.join(output_dir, "%s.tv" % dataFileName), "wb")
    buffer = bytearray(bytes(0x40))
    writeInt(0, buffer, 2, TV_FILE_VERSION)
    writeInt(4, buffer, 4, 1247551947)
    file.write(buffer)
    currentIndex = 0
    for entry in entries:
        file_name = entry[0]
        file_start_offset = currentIndex
        file_flag = entry[4]
        need_uncompress = file_flag & 1
        need_decrypt = (file_flag >> 1) & 1
        file_name = file_name.replace("\\", os.sep).replace("." + os.sep, ("%s" + os.sep) % input_dir)
        res_file = open(file_name, "rb")
        res_buffer = bytearray(res_file.read())
        file_origin_length = len(res_buffer)
        compressedBytes = res_buffer
        if need_decrypt == 1:
            compressedBytes = encryptXMLInMemory(compressedBytes)
        if need_uncompress == 1:
            compressedBytes = bytearray(zlib.compress(compressedBytes))
            compressedBytes.insert(0, 0) #第一个字节插入无用字符
            c = 0
            headIndex = 0
            length = compressedBytes.__len__()
            tailIndex = length - 1
            if length >= 0xD:
                while True:
                    tempByte = compressedBytes[tailIndex]
                    compressedBytes[tailIndex] = compressedBytes[headIndex]
                    compressedBytes[headIndex] = tempByte
                    tailIndex = tailIndex - 1
                    headIndex = headIndex + 1
                    c = c + 1
                    if c >= 0xD:
                        break
        file_after_length = len(compressedBytes)
        file.write(compressedBytes)
        entry[1] = file_start_offset
        entry[2] = file_after_length
        entry[3] = file_origin_length
        currentIndex = currentIndex + file_after_length
    file.close()

def unpackDataTvFile(path, entries):
    file = open(path, "rb")
    bytes = bytearray(file.read(0x40))
    version = readInt(0, bytes, 2)
    print("%s file version %d" % (path, version))

    for entry in entries:
        file_name = entry[0]
        file_start_offset = entry[1]
        file_read_length = entry[2]
        file_flag = entry[4]
        need_uncompress = file_flag & 1
        need_decrypt = (file_flag >> 1) & 1
        file_name = file_name.replace("\\", os.sep).replace("." + os.sep, ("%s" + os.sep) % output_dir)
        dirname = os.path.dirname(file_name)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        file.seek(0x40 + file_start_offset)
        bytes = bytearray(file.read(file_read_length))
        uncompressedBytes = bytes
        if need_uncompress == 1:
            c = 0
            headIndex = 0
            length = bytes.__len__()
            tailIndex = length - 1
            if length >= 0xD:
                while True:
                    tempByte = bytes[tailIndex]
                    bytes[tailIndex] = bytes[headIndex]
                    bytes[headIndex] = tempByte
                    tailIndex = tailIndex - 1
                    headIndex = headIndex + 1
                    c = c + 1
                    if c >= 0xD:
                        break
            bytes = bytes[1:]  # 第一个字节没用
            uncompressedBytes = bytearray(zlib.decompress(bytes))
        if need_decrypt == 1:
            uncompressedBytes = decryptXMLInMemory(uncompressedBytes)
        out = open(file_name, "wb")
        out.write(uncompressedBytes)
        out.close()
    file.close()

def unpack():
    tvFile = open(os.path.join(input_dir, "data15.tv"), "rb")
    byteArray = bytearray(tvFile.read(0x40))
    version = readInt(0, byteArray, 2)
    print("tv file version %d" % version)
    print("tv file size %d" % os.path.getsize(os.path.join(input_dir, "data15.tv")))
    tvFile.seek(-8, 2)
    size = readInt(0, bytearray(tvFile.read(0x4)), 4)
    nNumberOfBytesToRead = readInt(0, bytearray(tvFile.read(0x4)), 4)
    print("size %d" % size)
    print("nNumberOfBytesToRead %d" % nNumberOfBytesToRead)
    offset = 2098243 - (nNumberOfBytesToRead + 72) % 0x403
    print("offset %d" % offset)
    tvFile.seek(offset, 0)
    byteArray = bytearray(tvFile.read(nNumberOfBytesToRead))
    counter = 0
    headIndex = 0
    length = byteArray.__len__()
    tailIndex = length - 1
    if length >= 0xD:
        while True:
            temp = byteArray[tailIndex]
            byteArray[tailIndex] = byteArray[headIndex]
            byteArray[headIndex] = temp
            tailIndex = tailIndex - 1
            headIndex = headIndex + 1
            counter = counter + 1
            if counter >= 0xD:
                break
    tvFile.close()
    byteArray = byteArray[1:]  # 第一个字节没用
    uncompressedByteArray = zlib.decompress(byteArray)
    print(len(uncompressedByteArray))
    bufferIndex = 0
    dataFileNum, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 1, True)
    print("dataFileNum %d" % dataFileNum)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    rootFileEntries = []
    for j in range(0, dataFileNum):
        dataFileName, bufferIndex = readString(bufferIndex, uncompressedByteArray)
        fullDataFileName = os.path.join(input_dir, "%s.tv" % dataFileName)
        print("fullDataFileName %s" % fullDataFileName)
        uncompressedSize, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 4, True)
        print("uncompressedSize %d" % uncompressedSize)
        compressedSize, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 4, True)
        print("compressedSize %d" % compressedSize)
        unknownFlag, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 1, True)
        print(
            "unknownFlag %d &1=%d >>1&1=%d"
            % (unknownFlag, unknownFlag & 1, (unknownFlag >> 1) & 1)
        )
        entryNum, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 2, True)
        print("entryNum %d" % entryNum)
        rootFileEntries.append((dataFileName, unknownFlag))

        entries = []
        for i in range(0, entryNum):
            entryName, bufferIndex = readString(bufferIndex, uncompressedByteArray)
            startOffset, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 4, True)
            byteNum, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 4, True)
            maybeAfterSize, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 4, True)
            unknownFlag, bufferIndex = readInt(bufferIndex, uncompressedByteArray, 1, True)
            entries.append((entryName, startOffset, byteNum, maybeAfterSize, unknownFlag))
        if not only_debug:
            unpackDataTvFile(fullDataFileName, entries)
        configFile = os.path.join(output_dir, dataFileName + ".json")
        fd = open(configFile, "w")
        fd.write(json.dumps(entries))
        fd.close()
    entryConfigFile = os.path.join(output_dir, "entry.json")
    fd = open(entryConfigFile, "w")
    fd.write(json.dumps(rootFileEntries))
    fd.close()

def repack():
    entryConfigFile = os.path.join(input_dir, "entry.json")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    fd = open(entryConfigFile, "r")
    rootFileEntries = json.loads(fd.read())
    tempFileFd = open(os.path.join(input_dir, "temp"), "wb")
    for rootFileEntry in rootFileEntries:
        dataFileName = rootFileEntry[0]
        flag = rootFileEntry[1]
        configFile = os.path.join(input_dir, dataFileName + ".json")
        configFileFd = open(configFile, "r")
        entries = json.loads(configFileFd.read())
        configFileFd.close()
        repackDataTvFile(dataFileName, entries)
        writeString(tempFileFd, dataFileName)
        lastEntry = entries[len(entries) - 1]
        contentSize = lastEntry[1] + lastEntry[2]
        tempFileFd.write(int.to_bytes(contentSize, 4, "little"))
        tempFileFd.write(int.to_bytes(contentSize, 4, "little"))
        tempFileFd.write(int.to_bytes(flag, 1, "little"))
        tempFileFd.write(int.to_bytes(len(entries), 2, "little"))
        for entry in entries:
            writeString(tempFileFd, entry[0])
            tempFileFd.write(int.to_bytes(entry[1], 4, "little"))
            tempFileFd.write(int.to_bytes(entry[2], 4, "little"))
            tempFileFd.write(int.to_bytes(entry[3], 4, "little"))
            tempFileFd.write(int.to_bytes(entry[4], 1, "little"))
    fd.close()
    tempFileFd.close()

    tempFileFd = open(os.path.join(input_dir, "temp"), "rb")
    contentBuffer = bytearray(tempFileFd.read())
    contentBuffer.insert(0, int.to_bytes(len(rootFileEntries), 1, "little")[0])
    uncompressedByteLength = len(contentBuffer)
    compressedByteArray = bytearray(zlib.compress(contentBuffer))
    compressedByteArray.insert(0, 0)

    counter = 0
    headIndex = 0
    length = compressedByteArray.__len__()
    tailIndex = length - 1
    if length >= 0xD:
        while True:
            temp = compressedByteArray[tailIndex]
            compressedByteArray[tailIndex] = compressedByteArray[headIndex]
            compressedByteArray[headIndex] = temp
            tailIndex = tailIndex - 1
            headIndex = headIndex + 1
            counter = counter + 1
            if counter >= 0xD:
                break

    offset = 2098243 - (length + 72) % 0x403
    totalLength = offset + length + 8
    buffer = bytearray(bytes(totalLength))

    writeInt(0, buffer, 2, TV_FILE_VERSION)
    writeInt(4, buffer, 4, 1247551947)
    writeInt(totalLength - 8, buffer, 4, uncompressedByteLength)
    writeInt(totalLength - 4, buffer, 4, length)
    for i in range(0, length):
        buffer[i + offset] = compressedByteArray[i]
    print("uncompressedByteLength %d" % readInt(totalLength - 8, buffer, 4))
    print("byteLength %d" % readInt(totalLength - 4, buffer, 4))
    print("file size %d" % totalLength)
    entryTvFile = open(os.path.join(output_dir, "data15.tv"), "wb")
    entryTvFile.write(buffer)
    entryTvFile.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='script for tenvi tv files unpacking or repacking', usage='python3 tenvi_decrypt_tv.py --cmd unpack/repack --input_dir *** --output_dir ***')
    parser.add_argument('--cmd', action="store", dest="cmd", help='operation(unpack or repack)')
    parser.add_argument('--input_dir', action="store", dest="input_dir", help='tv files dir or unpacked files dir')
    parser.add_argument('--output_dir', action="store", dest="output_dir", help='output dir')
    parser.add_argument('--only_debug', action="store", dest="only_debug", help='dont actually write file')

    if len(sys.argv) == 1:
        results = parser.parse_args(['-h'])
    else:
        results = parser.parse_args()

    if results.only_debug:
        only_debug = True

    if results.input_dir:
        input_dir = results.input_dir
    else:
        exit("missing input_dir")
    
    if results.output_dir:
        output_dir = results.output_dir
    else:
        exit("missing output_dir")

    if results.cmd == "unpack":
        unpack()
    elif results.cmd == "repack":
        repack()
    else:
        exit("unsupport cmd")
