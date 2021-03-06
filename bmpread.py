import binascii
import math
import os
import base64
import hashlib
from pyZPL import *

imagedir = "images/"

#This is used to reverse the order of bytes when reading the header.
#This is necessary because, for example, the 4 bytes following offset 10 define where the
#pixel array begins. If it begins at 0x82, the 4 bytes read, in order: 82 00 00 00
#This is backwards; 0x82 is very different from 0x82000000 and so it must be reversed
def reverseByteArray(ba):
    newba = bytearray(len(ba))
    for i,b in enumerate(ba):
        newba[len(ba)-i-1] = b #Put bytes from beginning of ba at the end of newba
    return newba

def convertImg(image,imageName,width,height,ispwidth,ispheight,tempdir):
    dn = os.path.dirname(os.path.realpath(__file__))+"/"
    resizeCommand = "convert "+dn+imagedir+image+" -resize "
    resize = False

    if width is not 0:
        resizeCommand += str(width)
        if ispwidth:
            resizeCommand += '%'
        resize = True
    if height is not 0:
        resizeCommand += "x"+str(height)
        if ispheight:
            resizeCommand += '%'
        resize = True

    if resize:
        fileSplit = image.split('/')
        fileName = fileSplit[len(fileSplit)-1]
        resizeCommand += " "+tempdir+fileName
        os.system(resizeCommand)
        print resizeCommand
        command = "convert "+tempdir+fileName
    else:
        command = "convert "+dn+imagedir+image

    command += " -flatten -compress None -monochrome -colors 2 -depth 1 +dither "+tempdir+imageName+".bmp"
    os.system(command)
    print command

#Read image data, skips over padding and ensures that padding within bytes will end
#up being white (after inversion). Expects that inFile's pointer is at the beginning
#of the pixel array
def readImageData(rowsize,padding,width,inFile):
    EOF = False
    unpaddedImage = bytearray()
    i = 1

    #Undefined bits in the byte at the end of a row (not counting 4-byte padding)
    #A 100-pixel row's pixels take up 100 bits, or 12.5 bytes. This means that there
    #are 8*0.5 (4) unused bits at the end, which must be set to FF so that they will be
    #white after inversion later
    unusedBits = int((math.ceil(width/8.0)-(width/8.0))*8)

    #Binary mask to OR with the last byte; if there are 5 unused bits then the mask will
    #be 00011111
    unusedBitsMask = int(pow(2,unusedBits)-1)
    print bin(unusedBitsMask)
    while not EOF:
        try:
            readByte = int(binascii.hexlify(inFile.read(1)),16)
            if i == rowsize-padding:
                inFile.seek(padding,1) #Skip the padding at the end of the row
                i = 1
                unpaddedImage.append(readByte | unusedBitsMask)
            else:
                unpaddedImage.append(readByte)
                i += 1
        except ValueError:
            EOF = True
    return unpaddedImage

def getImg(image,width,height,ispwidth,ispheight,tempdir):
    img = ZPLImage()
    fileSplit = image.split('/')
    fileName = fileSplit[len(fileSplit)-1]
    imageSplit = fileName.split('.')
    imageName = str.join('.',imageSplit[:len(imageSplit)-1])
    print image
    print imageName
    convertImg(image,imageName,width,height,ispwidth,ispheight,tempdir)
    f = open(tempdir+imageName+".bmp","rb")

    f.seek(10)
    arrayoffset = reverseByteArray(bytearray(f.read(4))) #offset where the pixel data array is located

    f.seek(18)
    widthbytes = reverseByteArray(bytearray(f.read(4)))
    img.width = int(binascii.hexlify(widthbytes),16)
    heightbytes = reverseByteArray(bytearray(f.read(4)))
    img.height = int(binascii.hexlify(heightbytes),16)
    print str(img.width)+","+str(img.height)

    f.seek(34)
    sizebytes = reverseByteArray(bytearray(f.read(4)))
    size = int(binascii.hexlify(sizebytes),16) #Size of the pixel data array, including padding
    print "size: "+str(size)

    f.seek(int(binascii.hexlify(arrayoffset),16))
    rowsize = size/img.height
    padding = rowsize-int(math.ceil(img.width/8.0))
    imagedata = readImageData(rowsize,padding,img.width,f)
    reversedImage = bytearray()
    print "rowsize: "+str(rowsize)
    print "padding: "+str(padding)
    for i in range(0,img.height):
        for j in range(0,rowsize-padding):
            hexr = imagedata[i*(rowsize-padding)+j]^0xff #Invert the bits (colours) so that it prints properly
            #hex1 is the first hex digit in the byte, hex2 is the second
            hex1 = hexr>>4
            hex2 = hexr&0x0f

            #Reverse each hex digit, add them together and append them to the image
            #reversed_hexx are what results when you take the binary representation of the hex digit
            #and run it backwards; this is important because a hex digit is a chunk of 4 pixels, and
            #each hex digit must be internally reversed in order to reverse the order of the pixels
            reversed_hex1 = sum(1<<(4-1-k) for k in range(4) if hex1>>k&1)
            reversed_hex2 = sum(1<<(4-1-k) for k in range(4) if hex2>>k&1)
            concat = str(hex(reversed_hex1))[2]+str(hex(reversed_hex2))[2]
            print concat,
            reversedImage.append(int(concat,16))
        print '\n',
    #Run the image data string backwards
    imagedatastr = binascii.hexlify(reversedImage)[::-1]
    print imagedatastr

    if len(imagedatastr)%2 is not 0:
        print "damn"

    #Take the first 7 characters of a base32-encoded sha-1 hash of the image data,
    #and use that as the name when downloading. This ensures that the file names are always
    #7 or fewer characters (as per ZPL requirements) but have a very low chance of colliding
    img.downloadName = base64.b32encode(hashlib.sha1(imagedatastr).digest())[:7]
    img.downloadCmd = "~DGR:"+img.downloadName+".GRF,"+str(len(imagedatastr)/2)+","+str(int(math.ceil(img.width/8.0)))+","+imagedatastr
    print "image bytes per row: "+str(int(math.ceil(img.width/8.0)))
    return img
