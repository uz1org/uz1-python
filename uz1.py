#UZ1 Lossless Compression. "Unconventional ZIP" v0.95 Early Access. Authored by Jace Voracek. www.uz1.org

import os, binascii, operator, collections, sys
from os import path

#Uncomment to record logged output
#log = open("log.txt", "a")
#sys.stdout = log

def intro():
    print()
    print("===================================")
    print()
    print(" | | | |  |___ |  /   |")
    print(" | | | |    / /  /_/| |")
    print(" | | | |   / /      | |")
    print(" | \_/ |  / /___  __| |__")
    print(" \____/  /_____/ |_______|")
    print()
    print("===================================")
    print()
    print("UZ1 Lossless Compression (uz1.org) - by Jace Voracek")
    print("v0.95 Early Access - Nov 2021")
    print()
    print("NOTICE: The Python version of UZ1 currently has slow performance. Expect >1hr durations for files >1GB")
    print("Recommended: decompress files after compressing and verify checksum hashes match the original file.")
    print("No warranty is issued for the usage of this script. User assumes all risk.")
    print()
    print()

def printHelp():
    print("USAGE:")
    print()
    print("To compress: ")
    print("python3 uz1.py compress fileNameHere")
    print()
    print("To decompress: ")
    print("python3 uz1.py decompress fileNameHere.uz1")
    print()
    print("Beta feature: Add 'max' as a third parameter to reiterate compression/decompression")
    print()


def main():
    global arg2, outputFilename, currentIteration, doMaxIteration

    currentIteration = 0
    doMaxIteration = False

    intro()
    if int(sys.version[0]) < 3:
        print("ERROR: Please upgrade to Python 3 or a subsequent version in order to use UZ1. Exiting...")
    else:
        try:
            arg1 = sys.argv[1] #Required: 'compress' or 'decompress'
        except:
            arg1 = ""
        try:
            arg2 = sys.argv[2] #Required: Input filename
        except:
            arg2 = ""
        try:
            arg3 = sys.argv[3] #Optional: 'max' to iterate the compression until file no longer shrinks, or decompress all iterations fully
        except:
            arg3 = ""

        if (arg1 == "compress"):
            if(arg2 is not None):
                if (arg3 == "max"):
                    outputFilename = arg2 + "." + str(currentIteration) + ".uz1"
                    doMaxIteration = True
                else:
                    outputFilename = arg2 + ".uz1"
                if (not path.exists(arg2)):
                    print("Error: Input filename " + arg2 + " does not exist. Exiting...")
                elif (path.exists(outputFilename)):
                    print("Error: A file named " + outputFilename + " already exists in the current directory. Exiting...")
                elif(path.isdir(outputFilename)):
                    print("Directories are not supported. Exiting...")
                else:
                    if (doMaxIteration == True):
                        compressMax(arg2)
                    else:
                        compressMain(arg2)
            else:
                printHelp()
        elif (arg1 == "decompress"):
            if(arg2 is not None):
                if (arg3 == "max"):
                    outputFilename = arg2.split('.uz1')[0]
                    currentIteration = int(outputFilename.split('.')[-1])
                    currentIteration = currentIteration - 1
                    if (currentIteration == -1):
                        outputFilename = outputFilename.split('.')[0] + "." + outputFilename.split('.')[1]
                    else:
                        outputFilename = (outputFilename.split('.')[0] + "." + outputFilename.split('.')[1]) + "." + str(currentIteration) + ".uz1"
                    doMaxIteration = True
                else:
                    outputFilename = arg2.split('.uz1')[0]
                if (path.exists(outputFilename)):
                    print("Error: A file named " + outputFilename + " already exists. Exiting...")
                else:
                    if (doMaxIteration == True):
                        decompressMax(arg2)
                    else:
                        decompressMain(arg2)
        else:
            printHelp()


#Common vars
bitSize = 8 #Currently only supports eight bits or more
neededGetOpp = 3 #arbitrary
my_dict = {}
myDictOneLess = {}
sorted_dict = {}
segmentString = remainder = ""
getLimitOneLess = ((2**(bitSize-1))-1)
numOfBitsNeededToCompress = 32 #arbitrary
numOfChars = numOfLargestKey = 0
largestKey = unusedKeyOneLess = oppLargeKeyValue = oppLargeKey = goBeforeNextSection = inputFileSize = getDecompLargeChar = ""
alertedForUncompressedDataBlock = stillNeedBytes = False
dirtyRealBackup = "" #todo: clean

#Common vars for decompression
decompLargeChar = getCurrentKey = decompAddAsRemainder = beginningOfSegment = isValidBit = backupSegmentString = unusedCharInBackup = ""
amountBeforeReadingNextKey = numOfKeysFound = 0
decompGetLimitOneLess = ((2**(bitSize-1))-0)
justStarted = 1
needBackup = alreadyMadeBackup = False


def compressMain(arg2):
    global remainder, stillNeedBytes, segmentString, inputFileSize, alertedForUncompressedDataBlock

    #open file here
    print("Now compressing: " + arg2)
    inputFileSize = getFileSize(arg2)
    with open(arg2, 'rb') as f:
        #Read file as hex 16 bytes at a time
        entry = (str(binascii.hexlify(f.read(16))))[2:-1]
        while entry:
            if (stillNeedBytes == True):
                if entry.isalnum():
                    remainder += hex2bin(entry)
                    if (len(remainder) > numOfLargestKey):
                        getValuesForComp()
                        stillNeedBytes = False
            else:
                if entry.isalnum():

                    #1. Convert to binary
                    binaryString = hex2bin(entry)
                    #2. Process the remainder
                    processRemainder()
                    #3. Process binary until segment is full
                    processBinary(binaryString)

                    #Alert user if large chunck of uncompressed data is detected. UZ1 works best with frequent permutations of the bitSize.
                    if (alertedForUncompressedDataBlock == False):
                        if (len(segmentString) > (getLimitOneLess * bitSize) * 1000):
                            print()
                            print("Large chunk of uncompressed data detected... Processing this file will proably take a while.")
                            print("Pro tip: Compress large volumes of uncompressed data with another algorithm before using UZ1.")
                            print()
                            print("Still compressing...")
                            alertedForUncompressedDataBlock = True

                #Determine if the current segment is done
                if (isSegmentFinished() is True):
                    processFinishedSegment()
            #Ready for next set of 16 bytes
            entry = (str(binascii.hexlify(f.read(16))))[2:-1]

    #Is there still unprocessed data? End of file?
    if ((len(segmentString)) or (len(remainder)) > 0):
        #There's still data to process
        comp_processEndOfFileUnfinished()
    print("Finished! :-)")
    sizeDiff = int(inputFileSize) - int(getFileSize(outputFilename))
    if (sizeDiff >= 0):
        print("Output is " + getFileSize(outputFilename) + " bytes. Saved " + str(sizeDiff) + " bytes from original.")
    else:
        print("Output is " + getFileSize(outputFilename) + " bytes. Grew " + str(sizeDiff*-1) + " bytes from original.")
    print()


def compressMax(arg2):
    global inputFileSize, outputFilename, currentIteration, segmentString, remainder, my_dict, myDictOneLess

    compressMain(arg2)
    sizeDiff = int(inputFileSize) - int(getFileSize(outputFilename))

    while(sizeDiff >= 0):
        currentIteration = currentIteration + 1
        previousFile = outputFilename
        outputFilename = arg2 + "." + str(currentIteration) + ".uz1"

        #reset some vars
        segmentString = ""
        remainder = ""
        my_dict = {}
        myDictOneLess = {}

        compressMain(previousFile)
        sizeDiff = int(inputFileSize) - int(getFileSize(outputFilename))
        if (sizeDiff >= 0):
            os.remove(previousFile)
        else:
            os.remove(outputFilename)
            print("UZ1 compression maxed out. Last iteration had better results. Keeping: " + previousFile)
    print("Totally done! :)")


def decompResetVars():
    global my_dict,myDictOneLess,segmentString,numOfChars,numOfLargestKey,largestKey,decompLargeChar,getCurrentKey,decompAddAsRemainder,beginningOfSegment,unusedCharInBackup,binaryString
    global amountBeforeReadingNextKey,justStarted,getDecompLargeChar
    my_dict = {}
    myDictOneLess = {}
    segmentString = ""
    numOfChars = 0
    numOfLargestKey = 0
    largestKey = ""
    decompLargeChar = ""
    getCurrentKey = ""
    decompAddAsRemainder = ""
    beginningOfSegment = ""
    unusedCharInBackup = ""
    binaryString = ""
    getDecompLargeChar = ""
    amountBeforeReadingNextKey = 0
    justStarted = 1


def decompressMax(arg2):
    global inputFileSize, outputFilename, currentIteration, segmentString, remainder, my_dict, myDictOneLess, justStarted, binaryString

    decompressMain(arg2)
    while(currentIteration >= 0):
        decompResetVars()
        currentIteration = currentIteration - 1
        previousFile = outputFilename
        print()
        if (currentIteration == -1):
            outputFilename = outputFilename.split('.')[0] + "." + outputFilename.split('.')[1]
        else:
            outputFilename = outputFilename.split('.')[0] + "." + outputFilename.split('.')[1] + "." + str(currentIteration) + ".uz1"
        decompressMain(previousFile)
        os.remove(previousFile)
    print("Totally done! :)")


def fakeComp():
    global segmentString, remainder, largestKey, goBeforeNextSection, dirtyRealBackup, getDecompLargeChar

    #Write remainder to beginning instead of key. No compression here!
    fakeKey = remainder[:(bitSize - 1)]
    numOfFakeKey = checkNumOfTimesKeyOneLessInSegment(dirtyRealBackup, fakeKey)
    numOfDecompLargeChar = checkNumOfTimesKeyInSegment(dirtyRealBackup, getDecompLargeChar)
    segmentString = fakeKey + segmentString
    remainder = remainder[(bitSize - 1):]
    
    getOppOfDecompLargeChar = getOppOfChar(getDecompLargeChar)
    numOfOppOfDecompLargeChar = checkNumOfTimesKeyInSegment(dirtyRealBackup, getOppOfDecompLargeChar)

    #TODO: Check if remainder[0] is 0. If so, this segment won't need to grow by a bit.
    if (numOfOppOfDecompLargeChar is not None):
        if ((numOfFakeKey >= (bitSize * 2)) and (numOfDecompLargeChar == 0) and (numOfOppOfDecompLargeChar >= neededGetOpp)):
            segmentString = goBeforeNextSection + "0" + segmentString
            #This key is INVALID (rare). Grows by one bit.
        else:
            proceedWithFake()
    else:
        proceedWithFake()


def proceedWithFake():
    global remainder, segmentString, goBeforeNextSection
    getBitFromRemainder = remainder[0]
    remainder = remainder[1:]
    segmentString = goBeforeNextSection + getBitFromRemainder + segmentString


def getValuesForComp():
    global segmentString, numOfLargestKey, largestKey, goBeforeNextSection, dirtyRealBackup

    #todo: this is dirty
    dirtyRealBackup = segmentString
    
    numOfOppOfLargestKey = checkNumOfTimesKeyInSegment(dirtyRealBackup, str(getOppOfChar(largestKey)))
    
    if (numOfOppOfLargestKey is not None):
        if ((numOfLargestKey >= (bitSize * 2)) and (numOfLargestKey <= numOfBitsNeededToCompress) and (numOfOppOfLargestKey >= neededGetOpp)):
            canCompress = testBeforeRealComp()
            if (canCompress == True):
                realComp()
            else:
                fakeComp()
        else:
            fakeComp()
    else:
        fakeComp()
    goBeforeNextSection = ""
    finishSegment()


def processFinishedSegment():
    global my_dict, myDictOneLess, sorted_dict, numOfChars, remainder, largestKey, stillNeedBytes
    global numOfLargestKey, unusedKeyOneLess, oppLargeKeyValue, oppLargeKey, writeFakeFlag, getDecompLargeChar

    sorted_dict = collections.OrderedDict(sorted(my_dict.items(), key=operator.itemgetter(1)))
    largestKey = str(list(sorted_dict.keys())[-1])
    oppLargeKey = getOppOfChar(largestKey)
    unusedKeyOneLess = checkUnusedChar(myDictOneLess)
    numOfLargestKey = my_dict.get(str(largestKey))
    oppLargeKeyValue = str(my_dict.get(str(oppLargeKey)))

    #Check if more bytes are needed
    if (len(remainder) <= numOfBitsNeededToCompress):
        stillNeedBytes = True
    else:
        getValuesForComp()

    my_dict = {}
    sorted_dict = {}
    myDictOneLess = {}
    getDecompLargeChar = ""
    numOfChars = 0
    writeFakeFlag = False


def checkNumOfTimesKeyOneLessInSegment(segmentToCheck, keyToCheck):
    global getDecompLargeChar
    tempNumOfKeysFound = 0
    getDecompLargeChar = ""
    tempDecompLargeChar = ""
    for i in range(0, len(segmentToCheck), bitSize):
        key = segmentToCheck[i:i+bitSize]
        if (key[:-1] == (keyToCheck)):
            tempNumOfKeysFound += 1
            if (len(tempDecompLargeChar) < bitSize):
                tempDecompLargeChar += key[-1:]
    if (len(tempDecompLargeChar) == bitSize):
        getDecompLargeChar = tempDecompLargeChar
    return tempNumOfKeysFound


def checkNumOfTimesKeyInSegment(segmentToCheck, keyToCheck):
    tempNumOfKeysFound = 0
    for i in range(0, len(segmentToCheck), bitSize):
        key = segmentToCheck[i:i+bitSize]
        if (key == (keyToCheck)):
            tempNumOfKeysFound += 1
    return tempNumOfKeysFound


def debugCheckNumOfDictItemsInSegment(segmentToCheck):
    tempDictOneLess = {}
    for i in range(0, len(segmentToCheck), bitSize):
        key = segmentToCheck[i:i+bitSize]
        keyBefore = key
        key = key[:-1]
        if key in tempDictOneLess:
            val = tempDictOneLess.get(key)
            tempDictOneLess[key] = (val + 1)
        else:
            tempDictOneLess[key] = 1
    return len(tempDictOneLess.items())


def testBeforeRealComp():
    global segmentString, remainder, tempUnusedKeyOneLess, numOfLargestKey, largestKey, unusedKeyOneLess, goBeforeNextSection

    numOfBitSizeRemaining = bitSize
    tempUnusedKeyOneLess = largestKey
    segmentString2 = segmentString
    temp2_numOfBitSizeRemaining = numOfBitSizeRemaining

    for i in range(0, len(segmentString2), bitSize):
        currChar = segmentString2[i:i+bitSize]
        if (currChar == largestKey):
            if (temp2_numOfBitSizeRemaining > 0):
                temp2_numOfBitSizeRemaining -= 1
            currBin = "0"
            currChar = unusedKeyOneLess + currBin
            segmentString2 = segmentString2[:i] + currChar + segmentString2[i+bitSize:]
    segmentString2 = goBeforeNextSection + "1" + unusedKeyOneLess + segmentString2

    #We're going to read the whole string using unusedKeyOneLess
    temp_dictOneLess = {}
    temp_segmentString = segmentString2[(bitSize):]
    tempNumOfKeysFound = 0

    for i in range(0, len(temp_segmentString), bitSize):
        key = temp_segmentString[i:i+bitSize]
        key = key[:-1]

        if (key == (unusedKeyOneLess)):
            tempNumOfKeysFound += 1

        #Add to temp oneLess dict
        if key in temp_dictOneLess:
            val = temp_dictOneLess.get(key)
            temp_dictOneLess[key] = (val + 1)
        else:
            temp_dictOneLess[key] = 1
        #Dictionary will fill up before the entire string is read

        if (len(temp_dictOneLess.items()) == (getLimitOneLess)):
            #Check if length of second string matches first
            break

    #If the number of found keys here don't match the actual, DO NOT COMPRESS
    if (tempNumOfKeysFound != numOfLargestKey):
        #This does not match the needed numOfLargestKey
        canCompress = False
    else:
        #Matches! We're good to compress
        canCompress = True
    return canCompress


def getOppOfChar(charToCheck):
    if (charToCheck[-1:] == "1"):
        oppChar = charToCheck[:-1] + "0"
    else:
        oppChar = charToCheck[:-1] + "1"
    return oppChar


def realComp():
    global segmentString, remainder, largestKey, unusedKeyOneLess, goBeforeNextSection

    numOfBitSizeRemaining = bitSize
    numProcessed = 0

    for i in range(0, len(segmentString), bitSize):
        if (numProcessed <= numOfBitsNeededToCompress):
            currChar = segmentString[i:i+bitSize]
            if (currChar == largestKey):
                if (numOfBitSizeRemaining > 0):
                    currBin = getNextBinValueFromLargestKey()
                    numOfBitSizeRemaining -= 1
                else:
                    currBin = getNextBinValueFromRemainder()
                numProcessed += 1
                currChar = unusedKeyOneLess + currBin
                segmentString = segmentString[:i] + currChar + segmentString[i+bitSize:]
    #Write key to beginning.
    segmentString = goBeforeNextSection + unusedKeyOneLess + segmentString
    #We are confident that this is correct, so add 1.
    segmentString = "1" + segmentString
    #This key is VALID


def finishSegment():
    global segmentString, remainder, goBeforeNextSection

    binaryToWrite = segmentString + ""
    getRemainder = (len(binaryToWrite) % 8)

    if (getRemainder != 0 ):
        goBeforeNextSection = binaryToWrite[-getRemainder:]
        binaryToWrite = binaryToWrite[:-getRemainder]

    writeToFile(binascii.unhexlify(bin2hex(binaryToWrite)))
    segmentString = ""


def checkUnusedChar(sorted_dict):
    for k, v in sorted_dict.items():
        valueToCheck = k[:-1]
        if (k[-1] == "1"):
            valueToCheck = valueToCheck + "0"
        else:
            valueToCheck = valueToCheck + "1"
        if (str(sorted_dict.get(str(valueToCheck))) == "None"):
            return valueToCheck


def processRemainder():
    global remainder, segmentString
    #Process Remainder First Section - add to dict
    if (len(remainder) >= bitSize):
        remainingRemainderLength = len(remainder)
        while (remainingRemainderLength >= bitSize):
            if (isSegmentFinished() is True):
                processFinishedSegment()
            remainingRemainderLength = remainingRemainderLength - bitSize
            #If the following isn't true, the remainder isn't big enough to be added to dict
            if (len(remainder[0:bitSize]) == bitSize):
                addToDict(remainder[0:bitSize])
                segmentString += remainder[0:bitSize]
                remainder = remainder[bitSize:]


def comp_processEndOfFileUnfinished():
    global segmentString, remainder, goBeforeNextSection

    segmentString = goBeforeNextSection + segmentString + remainder
    while (len(segmentString) % 8 != 0):
        segmentString += "0"
    writeToFile(binascii.unhexlify(bin2hex(segmentString)))


def processBinary(binCode):
    global remainder, segmentString

    #first, add remainder to beginning
    binCode = remainder + binCode
    remainder = ""
    remainingBinLength = len(binCode)

    while (remainingBinLength > 0):
        if (remainingBinLength < bitSize):
            remainder = binCode
            break
        else:
            remainingBinLength = remainingBinLength - bitSize
            if (isSegmentFinished() is True):
                remainder = remainder + binCode
                binCode = ""
                remainingBinLength = len(binCode)
                processFinishedSegment()
            else:
                addToDict(binCode[0:bitSize])
                segmentString += binCode[0:bitSize]
                binCode = binCode[bitSize:]


def addToDict(key):
    global numOfChars, myDictOneLess

    if key != None:
        #Add to regular dict
        if key in my_dict:
            val = my_dict.get(key)
            my_dict[key] = (val + 1)
        else:
            my_dict[key] = 1
        numOfChars = numOfChars + 1

        #Add to oneLess dict
        key = key[:-1]
        if key in myDictOneLess:
            val = myDictOneLess.get(key)
            myDictOneLess[key] = (val + 1)
        else:
            myDictOneLess[key] = 1


#Common Functions

def hex2bin(hexCode):
    binCode = bin(int(hexCode, 16))[2:].zfill(len(hexCode) * 4)
    binCode = binCode[binCode.find('b')+1:]
    return binCode

def writeToFile(contentToWrite):
    with open(outputFilename, "ab") as myfile:
        myfile.write(contentToWrite)

def getFileSize(filePath):
    return str(os.path.getsize(filePath))

def bin2hex(binCode):
    hexCode = '%0*X' % ((len(binCode) + 3) // 4, int(binCode, 2))
    return hexCode

def isSegmentFinished():
    if (isDictOneLessFull() is True):
        return True
    else:
        return False

#Not needed as standalone function, but useful for keeping track of myDictOneLess
def isDictOneLessFull():
    if ( (len(myDictOneLess.items()) >= getLimitOneLess)):
        return True
    else:
        return False

def getNextBinValueFromRemainder():
    global remainder
    valueToReturn = remainder[0]
    remainder = remainder[1:]
    return valueToReturn

def getNextBinValueFromLargestKey():
    global tempUnusedKeyOneLess
    valueToReturn = tempUnusedKeyOneLess[0]
    tempUnusedKeyOneLess = tempUnusedKeyOneLess[1:]
    return valueToReturn




#DECOMP FUNCTIONS

def decompressMain(arg2):
    global remainder, stillNeedBytes, justStarted, binaryString, segmentString

    print("Now decompressing: " + arg2)
    lastEntryRead = ""

    with open(arg2, 'rb') as f:
        #Read file as hex 16 bytes at a time
        entry = (str(binascii.hexlify(f.read(16))))[2:-1]
        while entry:

            if entry.isalnum():
                #1. Convert to binary
                if (len(entry) != 32):
                    binaryString = hex2binSmall(entry)
                else:
                    binaryString = hex2bin(entry)

                #2. Process binary until segment is full
                decomp_processBinary(binaryString)

            #Determine if the current segment is done
            if (isDecompSegmentFinished() is True):
                decomp_processFinishedSegment()

            lastEntryRead = entry
            #Ready for next set of 16 bytes
            entry = (str(binascii.hexlify(f.read(16))))[2:-1]

        #Is there still unprocessed data? End of file?
        if ((len(segmentString)) or (len(remainder)) > 0):
            #There's still data to process
            decomp_processEndOfFileUnfinished()

        print("Finished! :-)")


def decomp_processRemainder():
    global remainder, segmentString

    #Process Remainder First Section - add to dict
    if (len(remainder) >= bitSize):
        remainingRemainderLength = len(remainder)
        while (remainingRemainderLength >= bitSize):
            if (isDecompSegmentFinished() is True):
                decomp_processFinishedSegment()

            remainingRemainderLength = remainingRemainderLength - bitSize
            addToDict(remainder[0:bitSize])
            segmentString += remainder[0:bitSize]
            remainder = remainder[bitSize:]



def decomp_processBinary(binCode):
    global remainder, segmentString, justStarted, decompLargeChar, getCurrentKey, decompAddAsRemainder, isValidBit

    if (justStarted == 1):
        #Determine whether valid
        if (len(segmentString) != 0):
            remainder = segmentString + remainder
            segmentString = ""
        if (len(remainder) == 0):
            #Get isValidBit from BinCode
            isValidBit = binCode[0]
            binCode = binCode[1:]

            getCurrentKey = binCode[0:(bitSize-1)]
            binCode = binCode[(bitSize-1):]
        else:
            if (len(remainder) < (bitSize)):
                #How many bits do we need?
                numOfBitsNeeded = (bitSize) - len(remainder)
                remainder += binCode[0:numOfBitsNeeded]
                binCode = binCode[numOfBitsNeeded:]
            isValidBit = remainder[0]
            remainder = remainder[1:]
            getCurrentKey = remainder[0:(bitSize-1)]
            remainder = remainder[(bitSize-1):]
        justStarted = 0

    tempRemainder = remainder #todo: this is dirty
    decomp_processRemainder()

    numProcessed = 0
    remainingRemLength = len(tempRemainder)
    while (remainingRemLength > 0):
        if (remainingRemLength < bitSize):
            break
        else:
            decompCurrChar = tempRemainder[0:bitSize]
            remainingRemLength -= bitSize
            if (numProcessed <= numOfBitsNeededToCompress):
                if (decompCurrChar[:-1] == getCurrentKey):
                    if (len(decompLargeChar) < (bitSize)):
                        decompLargeChar += decompCurrChar[-1:]
                    else:
                        decompAddAsRemainder += decompCurrChar[-1:]
                    numProcessed += 1
            tempRemainder = tempRemainder[(bitSize):]
    binCode = remainder + binCode
    remainder = ""
    remainingBinLength = len(binCode)

    while (remainingBinLength > 0):
        if (remainingBinLength < bitSize):
            remainder = binCode
            break
        else:
            remainingBinLength = remainingBinLength - bitSize
            if (isDecompSegmentFinished() is True):
                remainder = remainder + binCode
                binCode = ""
                remainingBinLength = len(binCode)
                decomp_processFinishedSegment()
            else:
                decompCurrChar = binCode[0:bitSize]
                #Determine if current char is getCurrentKey
                if (decompCurrChar[:-1] == getCurrentKey):
                    if (len(decompLargeChar) < (bitSize)):
                        decompLargeChar += decompCurrChar[-1:]
                    else:
                        decompAddAsRemainder += decompCurrChar[-1:]
                addToDict(binCode[0:bitSize])
                segmentString += binCode[0:bitSize]
                binCode = binCode[bitSize:]


#Use this if there's not very many characters at end
def hex2binSmall(hexCode):
    binCode = bin(int(hexCode, 16))[2:].zfill(len(hexCode) * 4)
    binCode = binCode[binCode.find('b')+1:]
    while (len(binCode)%8 != 0):
        binCode = "0" + binCode
    return binCode


def isDecompSegmentFinished():
    #This will be less than OneLessFull UNLESS the oppLarge isn't defined
    if (decompIsDictOneLessFull() is True):
        return True
    else:
        return False


def decompIsDictOneLessFull():
    global myDictOneLess, segmentString, backupSegmentString, alreadyMadeBackup, unusedCharInBackup

    if ( (len(myDictOneLess.items()) == int(decompGetLimitOneLess) - 1 ) ):
        if (alreadyMadeBackup == False):
            backupSegmentString = segmentString
            #Just made backup
            unusedCharInBackup = checkUnusedChar(myDictOneLess)
            alreadyMadeBackup = True

        if (decompSectionCheckRequirements() is False):
            #The dict is full and the key is false. Continue processing
            return True
        else:
            #The key is true, we're not done yet
            return False
    elif ( (len(myDictOneLess.items()) == int(decompGetLimitOneLess)) ):
        return True
    else:
        return False


def decompSectionCheckRequirements():
    global segmentString, getCurrentKey, numOfKeysFound, isValidBit, decompLargeChar, numOfLargeCharFound

    #Requirements have been met. This should only run if there are enough of the getCurrentKey
    numOfKeysFound = 0
    numOfLargeCharFound = 0
    for i in range(0, len(segmentString), bitSize):
        currChar = segmentString[i:i+bitSize]
        if (currChar[:-1] == getCurrentKey):
            numOfKeysFound += 1
        if (currChar == decompLargeChar):
            numOfLargeCharFound += 1
    if ((numOfKeysFound >= (bitSize * 2)) and (isValidBit == "1") and (numOfLargeCharFound == 0)):
        return True
    else:
        return False


def decompSection():
    global segmentString, getCurrentKey, numOfKeysFound, decompLargeChar, decompAddAsRemainder

    #Requirements have been met. This should only run if there are enough of the getCurrentKey
    numOfKeysFound2 = 0
    for i in range(0, len(segmentString), bitSize):
        currChar = segmentString[i:i+bitSize]
        if (currChar[:-1] == getCurrentKey):
            segmentString = segmentString[:i] + decompLargeChar + segmentString[i+bitSize:]
            numOfKeysFound2 += 1
    #For decompRemainder, we have to know the length of it.
    #When we write segmentString to file, there's a good chance that this won't fit.
    #The next real or fake key begins after this.
    if (numOfKeysFound > numOfKeysFound2):
        decompAddAsRemainder = decompAddAsRemainder[:-(numOfKeysFound - numOfKeysFound2)]
    segmentString += decompAddAsRemainder
    decompFinishSegment()


def decompFakeSegment():
    global segmentString, remainder, amountBeforeReadingNextKey, beginningOfSegment, needBackup, isValidBit, numOfLargeCharFound

    binaryToWrite = beginningOfSegment + segmentString + getCurrentKey + ""

    #If needBackup is true, it's part of the invalid (rare) scenario
    if (needBackup == False):
        #isValidBit goes to remainder. Not needed if this is a backup.
        binaryToWrite += isValidBit
    else:
        if (numOfLargeCharFound != 0):
            binaryToWrite += isValidBit
    getRemainder = (len(binaryToWrite) % 8)
    if (getRemainder != 0):
        beginningOfSegment = binaryToWrite[-getRemainder:]
    else:
        beginningOfSegment = ""

    amountBeforeReadingNextKey = len(beginningOfSegment)
    extractBeginOfRemainder = remainder[:amountBeforeReadingNextKey]
    if (getRemainder != 0):
        binaryToWrite = binaryToWrite[:-getRemainder]

    writeToFile((binascii.unhexlify(bin2hex(binaryToWrite))))
    segmentString = ""


def decompFinishSegment():
    global segmentString, remainder, amountBeforeReadingNextKey, beginningOfSegment, isValidBit, needBackup, numOfLargeCharFound

    if ((isValidBit == "1") and (numOfLargeCharFound == 0)):
        binaryToWrite = beginningOfSegment + segmentString + ""
        getRemainder = (len(binaryToWrite) % 8)
        if (getRemainder != 0):
            beginningOfSegment = binaryToWrite[-getRemainder:]
        else:
            beginningOfSegment = ""
        amountBeforeReadingNextKey = len(beginningOfSegment)
        #Get how much is left here
        extractBeginOfRemainder = remainder[:amountBeforeReadingNextKey]
        #This segment is solid. No need for backup
        if (getRemainder != 0):
            binaryToWrite = binaryToWrite[:-getRemainder]
        #Write file
        writeToFile(binascii.unhexlify(bin2hex(binaryToWrite)))
        segmentString = ""
    else:
        needBackup = True
        #I NEED BACKUP

#Thanks to https://stackoverflow.com/a/7440332
def remove_prefix(text, prefix):
    return text[len(prefix):] if text.startswith(prefix) else text


def decomp_processFinishedSegment():
    global my_dict, myDictOneLess, sorted_dict, numOfChars, segmentString, remainder, largestKey, numOfLargestKey, getCurrentKey, decompAddAsRemainder
    global justStarted, numOfKeysFound, needBackup, backupSegmentString, alreadyMadeBackup, decompLargeChar, unusedCharInBackup, getDecompLargeChar

    segmentAfterBackup = remove_prefix(segmentString, backupSegmentString)

    #todo: this is a dirty fix, need to correct later
    remainder2 = remainder

    sorted_dict = collections.OrderedDict(sorted(my_dict.items(), key=operator.itemgetter(1)))
    largestKey = str(list(sorted_dict.keys())[-1])
    numOfLargestKey = my_dict.get(str(largestKey))
    numOfOppOfDecompLargeChar = my_dict.get(str(getOppOfChar(decompLargeChar)))
    
    if (numOfOppOfDecompLargeChar is not None):
        if ((numOfKeysFound >= (bitSize * 2)) and (numOfOppOfDecompLargeChar >= neededGetOpp)):
            #We have enough keys
            #If the following is true, and the numOfKeysFound in backup is also true, we need to use the backup if numOfKeysFound is greater
            checkNumOfKeysInBackup = checkNumOfTimesKeyOneLessInSegment(backupSegmentString, getCurrentKey)
            if ((checkNumOfKeysInBackup >= (bitSize * 2)) and (checkNumOfKeysInBackup <= numOfKeysFound)):
                #The following determines if we need a backup
                if (unusedCharInBackup is not None):
                    if (unusedCharInBackup == decompLargeChar[:-1]):
                        remainder = segmentAfterBackup + remainder2
                        segmentString = backupSegmentString
                        #We're using backup
            decompSection()
        else:
            #Not enough keys
            decompFakeSegment()
    else:
        decompFakeSegment()

    if (needBackup == True):
        remainder = segmentAfterBackup + remainder2
        segmentString = backupSegmentString
        decompFakeSegment()

    my_dict = {}
    myDictOneLess = {}
    sorted_dict = {}
    decompLargeChar = ""
    getCurrentKey = ""
    decompAddAsRemainder = ""
    beginningOfSegment = ""
    backupSegmentString = ""
    getDecompLargeChar = ""
    justStarted = 1
    numOfChars = 0
    numOfKeysFound = 0
    needBackup = False
    alreadyMadeBackup = False


def decomp_processEndOfFileUnfinished():
    global segmentString, remainder, beginningOfSegment, getCurrentKey, beginningOfSegment, isValidBit
    #Check 3607923181.0697A9D5
    segmentString = beginningOfSegment + isValidBit + getCurrentKey + segmentString + remainder
    while (len(segmentString) % 8 != 0):
        segmentString = segmentString[:-1]
    writeToFile(binascii.unhexlify(bin2hex(segmentString)))

if __name__ == '__main__':
    main()
#Thanks for using UZ1! 🪖
