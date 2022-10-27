#UZ1 Lossless Compression. "Unconventional ZIP" v0.96a WIP. Authored by Jace Voracek. www.uz1.org
#This is experimental. Not the main UZ1 algorithm. Currently just for testing.
#Todo: Bug fixes for decompression regular scenario needed. Add recursive bit deducer.
#Needs performance optimization. Might help porting to golang.

# Compress Notes - Abstract for each of the three segment scenarios.
# At 126, bigChar16 turns to 7seq
# (7)(1 (real)) - (7 bits)(8 bits the extra)
# Shrinks by one bit
#
# After 127 is 128
# At 128, fake 7seq stays as 7seq
# (7)(0 (fake)) - (16 7seq)(128 is either 128 or 7seq, to show what the original fakeChar eighth bit was)
# Doesn't grow or shrink
#
# After 127 is a 7seq
# 7seq becomes bigChar16
# (8 bits remainder) - (bigChar16)(7seq)
# Grows by one since eighth bit of fakeChar is missing.
#
# Regular if neither a bigChar16 or 7seq is detected.

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
    print("v0.96a Experimental WIP branch - Oct 2022")
    print()
    print("WIP Notice: This version of UZ1 is intended for testing and development only.")
    print("Bugs persist. Decompression is currently disabled. Use uz1.py for functionality.")
    print("This experimental version may be a candidate to be adopted as the primary algorithm.")
    print()
    print("NOTICE: UZ1 Python currently has glacially slow performance. Expect >1hr durations for files >1GB.")
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
    global arg2, outputFilename, currentIteration, doMaxIteration, runningCompress

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
            runningCompress = True
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
            runningCompress = False
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
                        print("Decompress functionality currently disabled in WIP version.")
                    else:
                        new_decompressMain(arg2)
                        print("Decompress functionality currently disabled in WIP version.")
        else:
            printHelp()


#Common vars
bitSize = 8 #Currently only supports eight bits
neededGetOpp = 2 #arbitrary
my_dict = {}
myDictOneLess = {}
sorted_dict = {}
getLimitOneLess = ((2**(bitSize-1))-2) #126
numOfBitsNeededToCompress = 32 #arbitrary
numOfChars = numOfLargestKey = numOfCheckFakeKey = searchingForFakeCharOr128 = startedDecomp = dirtyNumOfRemBinLength = 0
segmentString = remainder = largestKey = unusedKeyOneLess = goBeforeNextSection = inputFileSize = getDecompLargeChar = globalProcessType = theBitsFrom7seq = lastCharAfter127 = firstChar = injectAfterThisChar = ""
alertedForUncompressedDataBlock = stillNeedBytes = typeCompress = getOneMoreBit = dirtyFix_afterFirstSeg = checkedFirstInDict = checkedSecondInDict = checkedThirdInDict = checkedFourthInDict = haveAlreadyChecked126 = False


#Common vars for decompression
decompLargeChar = getCurrentKey = decompAddAsRemainder = beginningOfSegment = isValidBit = backupSegmentString = unusedCharInBackup = ""
amountBeforeReadingNextKey = numOfKeysFound = 0
decompGetLimitOneLess = ((2**(bitSize-1))-0)
justStarted = 1
needBackup = alreadyMadeBackup = False


def compressMain(arg2):
    global remainder, stillNeedBytes, segmentString, inputFileSize, alertedForUncompressedDataBlock, typeCompress
    typeCompress = True

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

                    #Large chunck of uncompressed data detected. UZ1 works best with frequent permutations of 8 bits.
                    if (alertedForUncompressedDataBlock == False):
                        if (len(segmentString) > (getLimitOneLess * bitSize) * 1000):
                            print()
                            print("Large chunk of uncompressed data detected... Processing this file will take a while.")
                            print("Pro tip: Compress large volumes of uncompressed data with another algorithm before using UZ1.")
                            print()
                            print("Still compressing...")
                            alertedForUncompressedDataBlock = True

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
    #DEBUG
    #os.remove(outputFilename)


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


def getFifteenBits(segmentToCheck, keyToCheck):
    fifteenBits = ""
    for i in range(0, len(segmentToCheck), bitSize):
        key = segmentToCheck[i:i+bitSize]
        if (key[:-1] == keyToCheck):
            fifteenBits += key[-1:]
    return fifteenBits


def injectCharAfterThis(injectAfterThisChar, keyToInject):
    global segmentString
    for i in range(0, len(segmentString), bitSize):
        key = segmentString[i:i+bitSize]
        if (key == injectAfterThisChar):
            segmentString = segmentString[:i] + key + keyToInject + segmentString[i+bitSize:]
            break


def stepTwo_checkFor7seq(segmentString, checkFakeKey, my_dict, myDictOneLess):
    numOfCheckFakeKey = myDictOneLess.get(str(checkFakeKey))
    #print("stepTwo_checkFor7seq - " + "myDictOneLess: " + str(len(myDictOneLess)) + " numOfCheckFakeKey: " + str(numOfCheckFakeKey) + " checkFakeKey: " + checkFakeKey)
    if (numOfCheckFakeKey == 16):
        numOfCheckFakeKey0 = str(my_dict.get(str(checkFakeKey + "0")))
        numOfCheckFakeKey1 = str(my_dict.get(str(checkFakeKey + "1")))
        fifteenBits = getFifteenBits(segmentString, checkFakeKey)
        fifteenPartOne = fifteenBits[:7]
        fifteenPartTwo = fifteenBits[-8:]
        numOfCheckFakeKey0 = str(my_dict.get(str(fifteenPartOne + "0")))
        numOfCheckFakeKey1 = str(my_dict.get(str(fifteenPartOne + "1")))
    return numOfCheckFakeKey


def getValuesForComp():
    global segmentString, numOfLargestKey, largestKey
    global sorted_dict, unusedKeyOneLess, remainder, myDictOneLess, unusedKeyOneLess, bigCharSixteen
    global numOfSixteenDetected, numOfCheckFakeKey, injectAfterThisChar, dirtyFix_afterFirstSeg

    if (typeCompress == True):
        if (globalProcessType == "compress"):
            realCompSixteen()
            numOfSixteenDetected = 0
        elif (globalProcessType == "fakeComp7seq"): #ying yang method
            fakeComp7seq()
        elif (globalProcessType == "fakeComp128"):
            fakeComp128()
        else:
            regularFake()
    else:
        if (globalProcessType == "realKey"):
            decompReal()
        elif (globalProcessType == "fakeKey128_1"):
            #128 stays as 128
            injectCharAfterThis(injectAfterThisChar, (firstChar[1:8] + "1"))
            injectAfterThisChar = ""
        elif (globalProcessType == "fakeKey128_0"):
            #7seq turns back to 128
            injectCharAfterThis(injectAfterThisChar, (firstChar[1:8] + "0"))
            injectAfterThisChar = ""
        elif (globalProcessType == "fakeKey7seq"):
            fakeKey7seq()
        elif (globalProcessType == "decompRegular"):
            #Todo: Clean this
            if (dirtyFix_afterFirstSeg == False):
                segmentString += firstChar
                dirtyFix_afterFirstSeg = True
            else:
                segmentString = segmentString[8:] + firstChar
    finishSegment()


def realCompSixteen():
    global segmentString, remainder, largestKey, unusedKeyOneLess, goBeforeNextSection
    global bigCharSixteen, unusedKeyOneLess, tempLargerUnusedChar, tempCharFifteen

    #1. Get the unused char
    #2. First eight digits are the bigChar16
    #3. Next eight digits are from the remainder
    #4. Add a "1" after the key

    unusedCharOneLess = unusedKeyOneLessList[getBitFromRemainder()]
    whichCharIsLarger = whichBinIsLarger(unusedKeyOneLessList[0], unusedKeyOneLessList[1])
    tempLargerUnusedChar = unusedCharOneLess
    tempCharFifteen = bigCharSixteen
    numBitsRemaining = bitSize

    for i in range(0, len(segmentString), bitSize):
        currChar = segmentString[i:i+bitSize]
        if (currChar == bigCharSixteen):
            if (numBitsRemaining > 0):
                currBin = getNextBinValueFromCharFifteen()
                numBitsRemaining -= 1
            else:
                currBin = getNextBinValueFromRemainder()
            currChar = unusedCharOneLess + currBin
            segmentString = segmentString[:i] + currChar + segmentString[i+bitSize:]
    #Write unusedChar to beginning
    segmentString = goBeforeNextSection + "1" + unusedCharOneLess + segmentString


def fakeComp7seq():
    global segmentString, remainder, lastCharAfter127, theBitsFrom7seq, goBeforeNextSection
    lastPart = segmentString[-8:]
    segmentString = segmentString[:-8]

    for i in range(0, len(segmentString), bitSize):
        currChar = segmentString[i:i+bitSize]
        if (currChar[0:7] == lastPart[0:7]):
            currChar = theBitsFrom7seq[0:8]
            segmentString = segmentString[:i] + currChar + segmentString[i+bitSize:]

    #LAST SECTION of this is the bit that is missing from the eigth bit of fakeChar
    segmentString = goBeforeNextSection + theBitsFrom7seq[8:16] + segmentString + lastPart + lastCharAfter127[7:8]


def fakeComp128():
    global segmentString, remainder, lastCharAfter127, goBeforeNextSection

    #After 128, fake 7seq stays as 7seq
    #(7)(0 (fake)) - (15 7seq) (128 is either 128 or 7seq) to show what original eighth bit was
    #Doesn't grow or shrink

    fullKey = lastCharAfter127
    lastChar128 = segmentString[-8:]
    lastBitOflastChar128 = lastChar128[-1:]
    segmentString = segmentString[:-8]

    if (fullKey[-1:] == "0"):
        #0 uses 7seq
        insertChar = fullKey[0:7] + lastBitOflastChar128
        #print("fakeComp - Using 7seq (0)")
    else:
        #1 uses 128
        insertChar = lastChar128[0:7] + lastBitOflastChar128
        #print("fakeComp - Using 128 (1)")
    remainder = remainder[8:]
    segmentString = goBeforeNextSection + "0" + fullKey[0:7] + segmentString + insertChar


def regularFake():
    global remainder, tempRemainder, segmentString, goBeforeNextSection, lastCharAfter127
    remainder = remainder[8:]
    segmentString = goBeforeNextSection + lastCharAfter127 + segmentString


def processFinishedSegment():
    global my_dict, myDictOneLess, sorted_dict, numOfChars, remainder, largestKey, stillNeedBytes, unusedKeyOneLessList, numOfLargestKey, segmentString
    global unusedKeyOneLess, getDecompLargeChar, checkedFirstInDict, checkedSecondInDict, checkedThirdInDict, checkedFourthInDict

    sorted_dict = collections.OrderedDict(sorted(my_dict.items(), key=operator.itemgetter(1)))
    largestKey = str(list(sorted_dict.keys())[-1])
    unusedKeyOneLess = checkUnusedChar(myDictOneLess)
    numOfLargestKey = my_dict.get(str(largestKey))
    unusedKeyOneLessList = checkUnusedCharList(myDictOneLess)

    #Check if more bytes are needed
    if ((len(remainder) <= numOfBitsNeededToCompress) and (typeCompress == True)):
        stillNeedBytes = True
    else:
        getValuesForComp()

    my_dict = {}
    myDictOneLess = {}
    getDecompLargeChar = ""
    numOfChars = 0
    checkedFirstInDict = False
    checkedSecondInDict = False
    checkedThirdInDict = False
    checkedFourthInDict = False


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


def checkNumOfItemsOneLessInSegment(segmentToCheck):
    tempDict = {}
    for i in range(0, len(segmentToCheck), bitSize):
        key = segmentToCheck[i:i+(bitSize-1)]
        if key in tempDict:
            tempDict[key] = (tempDict.get(key) + 1)
        else:
            tempDict[key] = 1
    #print("Unused chars in checkNumOfItemsOneLessInSegment: " + str(checkUnusedCharList(tempDict)))
    return len(tempDict)


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
    global segmentString, remainder, goBeforeNextSection, startedDecomp, haveAlreadyChecked126

    goBeforeNextSection = ""
    if (runningCompress == False):
        startedDecomp = 1
    binaryToWrite = segmentString + ""
    getRemainder = (len(binaryToWrite) % 8)

    if (getRemainder != 0 ):
        goBeforeNextSection = binaryToWrite[-getRemainder:]
        binaryToWrite = binaryToWrite[:-getRemainder]

    writeToFile(binascii.unhexlify(bin2hex(binaryToWrite)))
    haveAlreadyChecked126 = False
    segmentString = ""


def checkUnusedCharList(sorted_dict):
    listToReturn = []
    for k,v in sorted_dict.items():
        valueToCheck = k[:-2]
        valueToCheck2 = valueToCheck + "00"
        if (str(sorted_dict.get(valueToCheck2)) == "None"):
            if valueToCheck2 not in listToReturn:
                listToReturn.append(valueToCheck2)
        valueToCheck2 = valueToCheck + "01"
        if (str(sorted_dict.get(valueToCheck2)) == "None"):
            if valueToCheck2 not in listToReturn:
                listToReturn.append(valueToCheck2)
        valueToCheck2 = valueToCheck + "10"
        if (str(sorted_dict.get(valueToCheck2)) == "None"):
            if valueToCheck2 not in listToReturn:
                listToReturn.append(valueToCheck2)
        valueToCheck2 = valueToCheck + "11"
        if (str(sorted_dict.get(valueToCheck2)) == "None"):
            if valueToCheck2 not in listToReturn:
                listToReturn.append(valueToCheck2)
    return listToReturn


def checkUnusedChar(sorted_dict):
    for k, v in sorted_dict.items():
        valueToCheck = k[:-1]
        if (k[-1] == "1"):
            valueToCheck = valueToCheck + "0"
        else:
            valueToCheck = valueToCheck + "1"
        if (str(sorted_dict.get(str(valueToCheck))) == "None"):
            return valueToCheck


def comp_processEndOfFileUnfinished():
    global segmentString, remainder, goBeforeNextSection, dirtyNumOfRemBinLength

    segmentString = goBeforeNextSection + segmentString + remainder
    while (len(segmentString) % 8 != 0):
        segmentString += "0"
    #Todo: clean this bugfix
    if (segmentString[-len(remainder):] != remainder):
        contentToWrite = segmentString + remainder
    else:
        contentToWrite = segmentString
    #Todo: Also clean this supernatural bug
    # if ((dirtyNumOfRemBinLength >= 8) and (segmentString[-8:] == "00000000")):
    #     contentToWrite = contentToWrite[:-8]
    writeToFile(binascii.unhexlify(bin2hex(contentToWrite)))


def processRemainder():
    global remainder, segmentString, startedDecomp, firstChar

    #Process Remainder First Section - add to dict
    if (len(remainder) >= bitSize):
        remainingRemainderLength = len(remainder)
        while (remainingRemainderLength >= bitSize):
            if (isSegmentFinished(remainder) is True):
                processFinishedSegment()
            remainingRemainderLength = remainingRemainderLength - bitSize
            #If the following isn't true, the remainder isn't big enough to be added to dict
            if (len(remainder[0:bitSize]) == bitSize):
                remChar = remainder[0:bitSize]
                if (startedDecomp == 1):
                    firstChar = remChar
                    startedDecomp = 0
                    segmentString += remChar
                else:
                    addToDict(remChar)
                    segmentString += remChar
                remainder = remainder[bitSize:]


def processBinary(binCode):
    global remainder, segmentString, startedDecomp, firstChar, dirtyNumOfRemBinLength

    #Add remainder to beginning
    binCode = remainder + binCode
    remainder = ""
    remainingBinLength = len(binCode)

    while (remainingBinLength > 0):
        if (remainingBinLength < bitSize):
            remainder = binCode
            dirtyNumOfRemBinLength += 1 #Todo: clean
            break
        else:
            remainingBinLength = remainingBinLength - bitSize
            if (isSegmentFinished((remainder + binCode)) is True):
                remainder = remainder + binCode
                binCode = ""
                remainingBinLength = 0
                processFinishedSegment()
            else:
                binChar = binCode[0:bitSize]
                if (startedDecomp == 1):
                    firstChar = binChar
                    startedDecomp = 0
                else:
                    addToDict(binChar)
                    segmentString += binChar
                binCode = binCode[bitSize:]


def addToDict(key):
    global numOfChars, myDictOneLess

    #Debug
    # global checkedFirstInDict, checkedSecondInDict, checkedThirdInDict, checkedFourthInDict
    # if (checkedFirstInDict == False):
    #     checkedFirstInDict = True
    # elif ((checkedFirstInDict == True) and (checkedSecondInDict == False)):
    #     checkedSecondInDict = True
    # elif ((checkedSecondInDict == True) and (checkedThirdInDict == False)):
    #     checkedThirdInDict = True
    # elif ((checkedThirdInDict == True) and (checkedFourthInDict == False)):
    #     checkedFourthInDict = True

    if key != None:
        #Add to regular dict
        if key in my_dict:
            my_dict[key] = (my_dict.get(key) + 1)
        else:
            my_dict[key] = 1
        numOfChars = numOfChars + 1

        #Add to oneLess dict
        key = key[:-1]
        if key in myDictOneLess:
            myDictOneLess[key] = (myDictOneLess.get(key) + 1)
        else:
            myDictOneLess[key] = 1


def isSegmentFinished(tempRemainder):
    global segmentString, remainder, my_dict, myDictOneLess, numOfSixteenDetected, lastCharAfter127
    global numOfCheckFakeKey, searchingForFakeCharOr128, checkFakeKey, globalProcessType, theBitsFrom7seq, getOneMoreBit
    global startedDecomp, firstChar, typeCompress, injectAfterThisChar, bigCharSixteen, haveAlreadyChecked126

    currentChar = segmentString[-8:]
    bigCharSixteen = ""

    if (typeCompress == False):
        currentChar = segmentString[-8:]
        if (len(myDictOneLess.items()) == 127):

            bitType = firstChar[0:1]
            key = firstChar[1:8]
            numOfKeys = myDictOneLess.get(str(key))

            #Check if there are any bigChar14
            numOfSixteenDetected = stepOne_checkForSixteen(my_dict)

            if ((numOfSixteenDetected == 1) and (getOneMoreBit == False)):
                #need to get the bit after this
                getOneMoreBit = True
                return False
            elif ((numOfSixteenDetected == 1) and (getOneMoreBit == True)):
                globalProcessType = "fakeKey7seq"
                return True

            #Check if it is compress type
            if (numOfKeys == 16):
                theBitsFrom7seq = getBitsFrom7seqInSegmentString(segmentString, key)
                numOfTimes = checkNumOfTimesKeyInSegment(segmentString, theBitsFrom7seq[0:8])

                if ((numOfTimes == 0) and (bitType == "1")):
                    globalProcessType = "realKey"
                    return True
                elif ((numOfTimes == 0) and (bitType == "0")):
                    #Need more bytes. Go to next 128 or 7seq
                    currentChar = segmentString[-8:]
                    if (injectAfterThisChar == ""):
                        injectAfterThisChar = currentChar
                    #If 7seq is discovered again, run 128_0 scenario

                    #Need to get which char is unused
                    if (currentChar[0:7] == key):
                        if (foundOne128 == True):
                            foundOne128 = False
                            globalProcessType = "fakeKey128_0"
                            return True
                        else:
                            foundOne128 = True
                            return False
                else:
                    #This is fake. Proceed with regular
                    globalProcessType = "decompRegular"
                    return True
            elif (numOfKeys == 17):
                #This only happens after 127 if we're in a 128_0 scenario.
                #7seq will turn back into 128
                if (currentChar[0:7] == key):
                        globalProcessType = "fakeKey128_0"
                        lastBit = segmentString[-1:]
                        segmentString = segmentString[:-8] + (checkUnusedCharList(myDictOneLess)[0] + lastBit)
                        return True
            else:
                #This is fake. Proceed with regular
                globalProcessType = "decompRegular"
                return True
        elif (len(myDictOneLess.items()) == 128):
            currentChar = segmentString[-8:]
            globalProcessType = "fakeKey128_1"
            return True
    else:
        lastCharAfter127 = tempRemainder[0:8]
        #Step 1. Check if the number of chars is equal to 126
        if ((len(myDictOneLess.items()) == 126) and (haveAlreadyChecked126 == False)):
            sortedDictOneLess = collections.OrderedDict(sorted(myDictOneLess.items(), key=operator.itemgetter(1)))
            unusedKeyOneLessList = checkUnusedCharList(sortedDictOneLess)
            numOfSixteenDetected = stepOne_checkForSixteen(my_dict)
            checkNumOfOpp = checkNumOfTimesKeyInSegment(segmentString, getOppOfChar(bigCharSixteen))
            if ((numOfSixteenDetected == 1) and (checkNumOfOpp >= neededGetOpp)):
                globalProcessType = "compress"
                return True
            haveAlreadyChecked126 = True
            #If there are not fifteen, need to go to 127
            #Need to go to 127 before this step...
            #Step 2: Check for 7seq remainder
        elif ((len(myDictOneLess.items()) == 127) and (searchingForFakeCharOr128 == 0)):
            checkFakeKey = tempRemainder[0:7]
            bitAfterCheckFakeKey = tempRemainder[7:8]
            #lastCharAfter127 = tempRemainder[0:8]
            numOfCheckFakeKey = stepTwo_checkFor7seq(segmentString, checkFakeKey, my_dict, myDictOneLess)
            theBitsFrom7seq = getBitsFrom7seqInSegmentString(segmentString, checkFakeKey)
            checkNumOfOpp = checkNumOfTimesKeyInSegment(segmentString, getOppOfChar(theBitsFrom7seq[0:8]))
            if ((numOfCheckFakeKey == 16) and (checkNumOfOpp >= neededGetOpp)):
                searchingForFakeCharOr128 = 1
                #Check if fakeKey is next or 128
                tempRemainder = tempRemainder[8:]
                theBitsFrom7seq = getBitsFrom7seqInSegmentString(segmentString, checkFakeKey)

                #Check if first eight bits exist in the segment.
                numOfTimesKeyInSegment = checkNumOfTimesKeyInSegment(segmentString, theBitsFrom7seq[0:8])
                if (numOfTimesKeyInSegment == 0):
                    #Check if opposite for firstEightBits exists
                    if (checkNumOfTimesKeyInSegment(segmentString, getOppOfChar(theBitsFrom7seq[0:8])) == 0):
                        globalProcessType = "regular"
                        return True
                else:
                    globalProcessType = "regular"
                    return True
            else:
                #No 16 detected
                globalProcessType = "regular"
                return True

        elif ((len(myDictOneLess.items()) == 127) and (searchingForFakeCharOr128 >= 1)):
            #checkFakeKey = tempRemainder[0:7]
            if (searchingForFakeCharOr128 == 1):
                #Line below is breaking regular comp if 2 ends up not being true
                segmentString = segmentString[:-8]
                searchingForFakeCharOr128 = 2
                return False
            elif (searchingForFakeCharOr128 == 2):
                if (currentChar[0:7] == checkFakeKey):
                    theBitsFrom7seq = getBitsFrom7seqInSegmentString(segmentString, checkFakeKey)
                    checkNumOfOpp = checkNumOfTimesKeyInSegment(segmentString, getOppOfChar(theBitsFrom7seq[0:8]))
                    checkNumOfReg = checkNumOfTimesKeyInSegment(segmentString, theBitsFrom7seq[0:8])
                    checkNumOfCurrentChar = checkNumOfTimesKeyInSegment(segmentString, currentChar)
                    numOfCheckFakeKey = stepTwo_checkFor7seq(segmentString, checkFakeKey, my_dict, myDictOneLess)
                    #Todo: Below numOfCheckFakeKey should be 16, but currently 18. 17 is fakeChar, 18 is next 7seq.
                    if ((checkNumOfOpp >= neededGetOpp) and (checkNumOfReg == 0) and (numOfCheckFakeKey == 18)):
                        #Don't need theBitsFrom7seq. This scenario grows since eighth bit of fakeChar will be missing.
                        globalProcessType = "fakeComp7seq"
                        print("Grow scenario: " + "checkNumOfReg: " + (theBitsFrom7seq[0:8]) + ": " + str(checkNumOfReg) + " checkNumOfOpp: " + getOppOfChar(theBitsFrom7seq[0:8]) + ": " + str(checkNumOfOpp) + " numOfCheckFakeKey: " + str(numOfCheckFakeKey) + " fakeKey: " + checkFakeKey + " currentChar: " + currentChar + ": " + str(checkNumOfCurrentChar))
                    else:
                        globalProcessType = "regular"
                    return True
        elif (len(myDictOneLess.items()) == 128):
            globalProcessType = "fakeComp128"
            theBitsFrom7seq = getBitsFrom7seqInSegmentString(segmentString, checkFakeKey)
            checkNumOfOpp = checkNumOfTimesKeyInSegment(segmentString, getOppOfChar(theBitsFrom7seq[0:8]))
            checkNumOfReg = checkNumOfTimesKeyInSegment(segmentString, theBitsFrom7seq[0:8])
            checkNumOfCurrentChar = checkNumOfTimesKeyInSegment(segmentString, currentChar)
            checkFakeKey = tempRemainder[0:7]
            numOfCheckFakeKey = stepTwo_checkFor7seq(segmentString, checkFakeKey, my_dict, myDictOneLess)
            tempRemainder = tempRemainder[8:]
            return True



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

def getBitFromRemainder():
    global remainder
    valToReturn = remainder[:1]
    remainder = remainder[1:]
    return int(valToReturn)

def whichBinIsLarger(val1, val2):
    decVal1 = int(bin2hex(val1 + "0"), 16)
    decVal2 = int(bin2hex(val2 + "0"), 16)
    if (decVal1 > decVal2):
        return val1
    else:
        return val2

def stepOne_checkForSixteen(dictToCheck):
    global bigCharSixteen
    numOfSixteenDetected = 0
    for key, value in dictToCheck.items():
        if (value == 16):
            bigCharSixteen = key
            numOfSixteenDetected += 1
    return numOfSixteenDetected

def getBitsFrom7seqInSegmentString(segmentToCheck, keyToCheck):
    tempNumOfKeysFound = 0
    tempBits = ""
    for i in range(0, len(segmentToCheck), bitSize):
        key = segmentToCheck[i:i+bitSize]
        if (key[:-1] == (keyToCheck)):
            tempBits += key[-1]
    return tempBits

def getNextBinValueFromRemainder():
    global remainder
    valueToReturn = remainder[0]
    remainder = remainder[1:]
    return valueToReturn

def getNextBinValueFromLargestKey():
    global tempUnusedKeyOneLess
    valToReturn = tempUnusedKeyOneLess[0]
    tempUnusedKeyOneLess = tempUnusedKeyOneLess[1:]
    return valToReturn

def getNextBinValueFromLargerUnusedChar():
    global tempLargerUnusedChar
    valToReturn = tempLargerUnusedChar[0]
    tempLargerUnusedChar = tempLargerUnusedChar[1:]
    return valToReturn

def getNextBinValueFromCharFifteen():
    global tempCharFifteen
    valToReturn = tempCharFifteen[0]
    tempCharFifteen = tempCharFifteen[1:]
    return valToReturn



#DECOMP FUNCTIONS

def decompReal():
    global segmentString, remainder, largestKey, goBeforeNextSection, myDictOneLess
    global bigCharSixteen, unusedKeyOneLess, tempLargerUnusedChar, firstChar

    key = firstChar[1:8]
    unusedKeyOneLess = checkUnusedCharList(myDictOneLess)[0]
    theBitsFrom7seq = getBitsFrom7seqInSegmentString(segmentString, key)
    largerChar = whichBinIsLarger(key, unusedKeyOneLess)

    if (largerChar == key):
        bitToUse = 1
    else:
        bitToUse = 0

    for i in range(0, len(segmentString), bitSize):
        currChar = segmentString[i:i+bitSize]
        if (currChar[0:7] == key):
            currChar = theBitsFrom7seq[0:8]
            segmentString = segmentString[:i] + currChar + segmentString[i+bitSize:]
    segmentString += str(bitToUse) + theBitsFrom7seq[8:16]


def fakeKey7seq():
    global segmentString, remainder, largestKey, goBeforeNextSection, myDictOneLess
    global bigCharSixteen, unusedKeyOneLess, tempLargerUnusedChar
    global firstChar, my_dict, bigCharSixteen

    unusedKeyOneLess = checkUnusedCharList(myDictOneLess)[0]
    lastChar = (segmentString[-16:])[0:8]
    charToProcess = bigCharSixteen + firstChar
    myDictOneLess = {}
    alreadyAddedKey  = False

    for i in range(0, len(segmentString), bitSize):
        currChar = segmentString[i:i+bitSize]
        addToDict(currChar)
        if (len(myDictOneLess.items()) == 126):
            if (alreadyAddedKey == False):
                segmentString = segmentString[:i] + currChar + lastChar + segmentString[i+bitSize:]
            alreadyAddedKey = True
        if (currChar == bigCharSixteen):
            currChar = lastChar[0:7] + charToProcess[0:1]
            charToProcess = charToProcess[1:]
            segmentString = segmentString[:i] + currChar + segmentString[i+bitSize:]
    remainder = (segmentString[-8:])[1:8] + remainder
    segmentString = segmentString[:-8]


def new_decompressMain(arg2):
    global segmentString, remainder, stillNeedBytes, inputFileSize
    global alertedForUncompressedDataBlock, startedDecomp, typeCompress

    startedDecomp = 1
    typeCompress = False

    print("Now decompressing: " + arg2)
    inputFileSize = getFileSize(arg2)
    with open(arg2, 'rb') as f:
        #Read file as hex 16 bytes at a time
        entry = (str(binascii.hexlify(f.read(16))))[2:-1]
        while entry:
            if entry.isalnum():

                #1. Convert to binary
                binaryString = hex2bin(entry)
                #2. Process the remainder
                processRemainder()
                #3. Process binary until segment is full
                processBinary(binaryString)

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
    #Debug:
    #Test1: jp1.zip - 3,987,676,607 bytes - CRC32: 73E09542
    #Test2: jp2.7z - 3,989,683,717 bytes - CRC32: 69735B77
    #os.remove(outputFilename)

if __name__ == '__main__':
    main()
#Thanks for using UZ1! 🪖
