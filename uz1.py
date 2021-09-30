#UZ1 Lossless Compression. "Unconventional ZIP" v0.91 Early Access. Authored by Jace Voracek. www.uz1.org

#This script is highly unpolished. Same energy: https://xkcd.com/1513/

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
    print("v0.91 Early Access - Sep 2021")
    print()
    print("NOTICE: The Python version of UZ1 currently has slow performance. Expect >1hr durations for files >1GB")
    print("Suggestion: decompress files after compressing and verify checksum hashes match the original file.")
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
    global arg2
    global outputFilename
    global currentIteration
    global doMaxIteration

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
bitSize = 8
my_dict = {}
myDictOneLess = {}
sorted_dict = {}
copyOfDictOneLess = {}
segmentString = remainder = ""
getLimitOneLess = ((2**(bitSize-1))-1)
numOfBitsNeededToCompress = 32 #arbitrary
numOfChars = numOfLargestKey = 0
writeFakeFlag = mustWriteZero = stillNeedBytes = False
largestKey = unusedKeyOneLess = oppLargeKeyValue = oppLargeKey = goBeforeNextSection = inputFileSize = ""
dirtyRealBackup = "" #todo: clean
alertedForUncompressedDataBlock = False

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
                        determineIfFakeFlagNeeded(remainder[:(bitSize - 1)])
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
        print("Output is " + getFileSize(outputFilename) + " bytes. Grew " + str(sizeDiff) + " bytes from original.")
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
    global amountBeforeReadingNextKey, justStarted
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
    amountBeforeReadingNextKey = 0
    justStarted = 1


def decompressMax(arg2):
    global inputFileSize, outputFilename, currentIteration, segmentString, remainder, my_dict, myDictOneLess, justStarted, binaryString

    decompressMain(arg2)
    while(currentIteration >= 0):
        decompResetVars()
        currentIteration = currentIteration - 1
        previousFile = outputFilename
        print("currentIteration: " + str(currentIteration))
        print("previousFile: " + previousFile)
        if (currentIteration == -1):
            outputFilename = outputFilename.split('.')[0] + "." + outputFilename.split('.')[1]
        else:
            outputFilename = outputFilename.split('.')[0] + "." + outputFilename.split('.')[1] + "." + str(currentIteration) + ".uz1"
        decompressMain(previousFile)
        os.remove(previousFile)
    print("Totally done! :)")


def fakeComp():
    global segmentString, remainder, largestKey, goBeforeNextSection, writeFakeFlag, mustWriteZero, dirtyRealBackup

    bitsToProcess = ""
    numOfBitSizeRemaining = bitSize
    tempUnusedKeyOneLess = largestKey
    #Write remainder to beginning instead of key. No compression here!
    segmentString = remainder[:(bitSize - 1)] + segmentString
    fakeKey = remainder[:(bitSize - 1)]
    remainder = remainder[(bitSize - 1):]

    if (writeFakeFlag == True):
        segmentString = goBeforeNextSection + "0" + segmentString
        #This key is INVALID (rare)
    else:
        if (mustWriteZero == True):
            #Check for rare scenario if fake key is used too much
            numOfFakeKey = checkNumOfTimesKeyInSegment(dirtyRealBackup, fakeKey)
            if (numOfFakeKey >= (bitSize * 2) ):
                segmentString = goBeforeNextSection + "0" + segmentString
                #This key is INVALID (rare)
            else:
                #Need to get the next bit from remainder as the key
                getBitFromRemainder = remainder[0]
                remainder = remainder[1:]
                segmentString = goBeforeNextSection + getBitFromRemainder + segmentString
        else:
            #Need to get the next bit from remainder as the key
            getBitFromRemainder = remainder[0]
            remainder = remainder[1:]
            segmentString = goBeforeNextSection + getBitFromRemainder + segmentString


def getValuesForComp():
    global segmentString, numOfLargestKey, largestKey, goBeforeNextSection, dirtyRealBackup
    #temp
    global myDictOneLess
    bitsToProcess = ""
    numOfBitSizeRemaining = bitSize
    #todo: this is dirty
    dirtyRealBackup = segmentString

    if (numOfLargestKey >= (bitSize * 2)):
        canCompress = testBeforeRealComp()
        if (canCompress == True):
            realComp()
        else:
            fakeComp()
    else:
        fakeComp()
    goBeforeNextSection = ""
    finishSegment()


def determineIfFakeFlagNeeded(keyToCheck):
    global numOfLargestKey, remainder, copyOfDictOneLess, writeFakeFlag

    remainderToCheck = ""
    amountRemainderToCheck = 0
    if (numOfLargestKey is None):
        numOfLargestKey = 0
    if (numOfLargestKey < (bitSize * 2)):
        remainderToCheck = keyToCheck
        if (str(copyOfDictOneLess.get(str(remainderToCheck))) != "None"):
            amountRemainderToCheck = int(str(copyOfDictOneLess.get(str(remainderToCheck))))
            if (amountRemainderToCheck >= (bitSize * 2)):
                #The key is fake
                writeFakeFlag = True
            else:
                writeFakeFlag = False
        else:
            writeFakeFlag = False
    else:
        writeFakeFlag = False
    copyOfDictOneLess = {}

def processFinishedSegment():
    global my_dict, myDictOneLess, sorted_dict, numOfChars, remainder, largestKey, stillNeedBytes
    global numOfLargestKey, unusedKeyOneLess, oppLargeKeyValue, oppLargeKey, writeFakeFlag, copyOfDictOneLess

    sorted_dict = collections.OrderedDict(sorted(my_dict.items(), key=operator.itemgetter(1)))
    largestKey = str(list(sorted_dict.keys())[-1])
    oppLargeKey = getOppOfChar(largestKey)
    unusedKeyOneLess = checkUnusedChar(myDictOneLess)
    numOfLargestKey = my_dict.get(str(largestKey))
    oppLargeKeyValue = str(my_dict.get(str(oppLargeKey)))
    copyOfDictOneLess = myDictOneLess

    #Check if more bytes are needed
    if (len(remainder) <= numOfBitsNeededToCompress):
        stillNeedBytes = True
    else:
        determineIfFakeFlagNeeded(remainder[:(bitSize - 1)])
        getValuesForComp()

    my_dict = {}
    sorted_dict = {}
    myDictOneLess = {}
    numOfChars = 0
    writeFakeFlag = False


def checkNumOfTimesKeyInSegment(segmentToCheck, keyToCheck):
    tempNumOfKeysFound = 0
    for i in range(0, len(segmentToCheck), bitSize):
        key = segmentToCheck[i:i+bitSize]
        if (key[:-1] == (keyToCheck)):
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
    global segmentString, remainder, tempUnusedKeyOneLess, numOfLargestKey, largestKey, unusedKeyOneLess, goBeforeNextSection, mustWriteZero

    bitsToProcess = ""
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
    testOutputSegment = ""
    tempNumOfKeysFound = 0

    for i in range(0, len(temp_segmentString), bitSize):
        key = temp_segmentString[i:i+bitSize]
        testOutputSegment += key
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
        mustWriteZero = True
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
    bitsToProcess = ""
    numOfBitSizeRemaining = bitSize

    #todo: see if the following can be achieved without breaking fakeKey during decompress. saves one bit if opp of largest key exists
    # if (str(my_dict.get(str(getOppOfChar(largestKey)))) != "None"):
    # numOfBitSizeRemaining -= 1
    # print("realComp: opp of key exists")

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
    #print("endOfFile segmentString: " + segmentString)
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
    global remainder, stillNeedBytes, justStarted

    #debug
    global binaryString, segmentString

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
            #todo: this is a dirty fix
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
    global segmentString, getCurrentKey, numOfKeysFound, isValidBit

    #Requirements have been met. This should only run if there are enough of the getCurrentKey
    numOfKeysFound = 0
    for i in range(0, len(segmentString), bitSize):
        currChar = segmentString[i:i+bitSize]
        if (currChar[:-1] == getCurrentKey):
            numOfKeysFound += 1
    if ((numOfKeysFound >= (bitSize * 2)) and (isValidBit == "1")):
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

    #The decompRemainder is kinda weird. We have to know the length of it.
    #When we write segmentString to file, there's a pretty good chance that this won't fit.
    #The next real or fake key begins after this.
    if (numOfKeysFound > numOfKeysFound2):
        decompAddAsRemainder = decompAddAsRemainder[:-(numOfKeysFound - numOfKeysFound2)]
    segmentString += decompAddAsRemainder
    decompFinishSegment()


def decompFakeSegment():
    global segmentString, remainder, getCurrentKey, amountBeforeReadingNextKey, beginningOfSegment, needBackup, isValidBit

    binaryToWrite = beginningOfSegment + segmentString + getCurrentKey + ""

    #If needBackup is true, it's part of the invalid (rare) scenario
    if (needBackup == False):
        binaryToWrite = beginningOfSegment + segmentString + getCurrentKey + ""
        #isValidBit goes to remainder. Not needed if this is a backup.
        binaryToWrite += isValidBit
        #Added bit in front here (not backup)

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
    global segmentString, remainder, amountBeforeReadingNextKey, beginningOfSegment, isValidBit, needBackup

    if (isValidBit == "1"):
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
    global justStarted, numOfKeysFound, needBackup, backupSegmentString, alreadyMadeBackup, decompLargeChar, unusedCharInBackup

    segmentAfterBackup = remove_prefix(segmentString, backupSegmentString)

    #todo: this is a dirty fix, need to correct later
    remainder2 = remainder

    sorted_dict = collections.OrderedDict(sorted(my_dict.items(), key=operator.itemgetter(1)))
    largestKey = str(list(sorted_dict.keys())[-1])
    numOfLargestKey = my_dict.get(str(largestKey))

    if (numOfKeysFound >= (bitSize * 2) ):
        #We have enough keys
        #If the following is true, and the numOfKeysFound in backup is also true, we need to use the backup if numOfKeysFound is greater
        checkNumOfKeysInBackup = checkNumOfTimesKeyInSegment(backupSegmentString, getCurrentKey)
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
