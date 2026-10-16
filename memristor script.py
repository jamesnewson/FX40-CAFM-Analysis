from SmartRemote import SmartRemote as SR
import numpy as np
import matplotlib.pyplot as plt
from json import dumps
import os
from TIFF_Read_Write import Read_tiff
import time
import logging
import math

reader = Read_tiff()
sr = SR()

# check if SmartRemote is connected
connection = sr.check_connection()
print(f"SmartRemote is {connection}")
# check if PowerScript is running
result = sr.check_status()
print(f"PowerScript running is {result}")


def square_spiral(max_coordinate=80):
	"""Yield points starting at (0, 0), ending at the first visit to (80, 80)."""
	x = y = 0
	yield x, y

	step_length = 1
	directions = ((1, 0), (0, 1), (-1, 0), (0, -1))
	while True:
		for dx, dy in directions:
			for _ in range(step_length):
				x += dx
				y += dy
				yield x, y
				if (x, y) == (max_coordinate, max_coordinate):
					return
			# Increase the length after each pair of directions.
			if dy != 0:
				step_length += 1

def changeSetpoint(setpoint):
    """
    This function changes the deflection setpoint for the IV measurement in normalized units (V).
    
    Parameters:
    setpoint (float): The new deflection setpoint value.

    Returns:
    None
    """

    setpointScript = f"spm.zservo.setpoint.normValue = {setpoint}"
    sr.run(setpointScript)

def moveToLocation(location):
    """
    This function moves the stage to a specified (x, y) location.
    
    Parameters:
    location (list): A list containing the (x, y) coordinates to move the stage to.

    Returns:
    None
    """
    locScript = f"spm.xyscanner.moveTo({location[0]},{location[1]},1,1)"
    sr.run(locScript)

def updateDirectory(baseDir, subDir, fileName):
    """
    This function updates the directory for saving IV measurement data based on the specified area.
    
    Parameters:
    baseDir (str): The base directory for saving IV measurement data.
    subDir (str): The subdirectory for saving IV measurement data.
    fileName (str): The name of the file to save the data to.

    Returns:
    None
    """
    loc = {'baseDir': baseDir,
            'subDir': f'{subDir}',
            'cameraSave': False,
            'direction': 'auto',
            'fileName' : fileName,
            'fileSuffix':' %1_%G_%N',
            'jpegSave': False,
            'precision':1,
            }
    jsonLoc = dumps(loc)
    sr.run(f'spm.dataLocation={jsonLoc}')

def analyzeData(baseDir, subDir):
    """
    This function analyzes the last created IV spectroscopy TIFF and checks if it is an open circuit or short circuit.
    
    Parameters:
    baseDir (str): The base directory where the IV measurement data is saved.
    subDir (str): The subdirectory where the IV measurement data is saved.

    Returns:
    result (str): A string indicating whether the last IV measurement is an open circuit ("OC"), short circuit ("SC"), or molecular ("MC").
    
    """
    # Get the list of files in the specified directory
    dirPath = os.path.join(baseDir, subDir)
    files = [f for f in os.listdir(dirPath) if f.endswith('.tiff')]
    
    if not files:
        print("No TIFF files found in the specified directory.")
        return None
    
    # Sort files by creation time and get the last created file
    files.sort(key=lambda x: os.path.getctime(os.path.join(dirPath, x)))
    lastFile = files[-1]
    #print(lastFile)

    # Read the last created TIFF file
    spectDict, spectTiff = reader(os.path.join(dirPath, lastFile))

    # Analyze the spectroscopy data to determine if it is an open circuit or short circuit
    v = np.abs(spectDict['SPECT_DATA'][0][0]) # Voltage data in V
    j = np.abs(spectDict['SPECT_DATA'][0][1]) # Current data in nA
    for i in range(len(v)):
        if 0 < v[i] < 0.2 and j[i] > 9000:
            #print("Short")
            return "SC"  # Short Circuit
        elif 1.8 < v[i] < 2.0 and j[i] < 0.5:
            #print("Open")
            return "OC"  # Open Circuit
    #print("Molecular")
    return "MC"  # Molecular

def startIV(sequence, writeVoltage=-2, readVoltage=-0.5, eraseVoltage=2):
    """
    This function starts the IV measurement process for a memristor device.
    
    Parameters:
    sequence (list): A list containing the sequence of operations to perform during the IV measurement, READ, WRITE, ERASE.
    writeVoltage (float): The voltage to use for the WRITE operation.
    readVoltage (float): The voltage to use for the READ operation.
    eraseVoltage (float): The voltage to use for the ERASE operation.

    Returns:
    None
    """

    params = {
	    "bias": { #bias settings
		    "isReversed": False, #true= lowest highest, false= highest to lowest
		    "highest":2, #V, set highest bias value
		    "lowest":-1.5, #V, set lowest bias value 
		    "useStartEndSplit": False, #true: use bias split, false: start=end bias 
			"start":0, #V, set start bias value
			"end":0}, #V, set end bias value

	    "usePeriod": True, # true= use period, false= use speed
		    "period": 0.25, # sec, set period value
		    "speed": 3, # V/s, set speed value

	    "limit":{ #current limit settings
		    "enabled":False, #true= current limit enabled, false=current limit disabled
		    "current":3}, #nA, set current limit

	    "lift":{ #lift height settings
		    "enabled": False, #true= lift height enabled, false= lift height disabled
		    "height":3}, #nm, set lift height

	"channels":["Sample Bias", "Current", "Time Stamp"], #set channels
	"pixels": 1024,
	"isLaserOff": False}

    jsonParams = dumps(params)
    sr.run(f"spm.spect.iv = {jsonParams}")
    sr.run("spm.spect.start('iv')")
    for operation in sequence:
        if operation == "WRITE":
            params["bias"]["highest"] = 0
            params["bias"]["lowest"] = writeVoltage
        elif operation == "READ":
            params["bias"]["highest"] = 0
            params["bias"]["lowest"] = readVoltage
        elif operation == "ERASE":
            params["bias"]["highest"] = eraseVoltage
            params["bias"]["lowest"] = 0
        else:
            print(f"Unknown operation: {operation}")
            continue

        jsonParams = dumps(params)
        #print(f"Starting {operation} operation with parameters: {params['bias']}")
        sr.run(f"spm.spect.iv = {jsonParams}")
        sr.run("spm.spect.start('iv')")
        time.sleep(0.01)
    params["bias"]["highest"] = 2
    params["bias"]["lowest"] = -1.5
    jsonParams = dumps(params)
    sr.run(f"spm.spect.iv = {jsonParams}")
    sr.run("spm.spect.start('iv')")


coords = list(square_spiral(80))

baseDir = r"D:\SpmData\Lancaster\2026-10-15 JN fP2\Memristor measurements"
os.makedirs(baseDir)

logPath = os.path.join(baseDir, "memristor_log.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(logPath, encoding="utf-8"),
        logging.StreamHandler(),  # Also show messages in the terminal
    ],
)
logger = logging.getLogger(__name__)

sequence = ["WRITE", "READ", "ERASE", "READ"]
setpoint = 0.6
area = 0
SC = 0
OC = 0
loops = 0

updateDirectory(baseDir, str(area), "iv")
changeSetpoint(setpoint)
moveToLocation(coords[area])

writeVoltage=-1.5
readVoltage=-0.5 
eraseVoltage=2

logger.info("Starting Measurement")
logger.info(f"Write voltage is {writeVoltage}, Read Voltage is {readVoltage}, erase voltage is {eraseVoltage}")
logger.info(f"The sequence is {sequence}")

try:
    while area < len(coords):
        startIV(sequence, writeVoltage, readVoltage, eraseVoltage)
        #time.sleep(1)
        result = analyzeData(baseDir, str(area))
        loops += 1
        if result == "SC":
            SC += 1
            OC = 0
            logger.info(f"Area {area} is a short circuit after {loops} loops. Moving to next area.")
            area += 1
            if area < len(coords):
                moveToLocation(coords[area])
                updateDirectory(baseDir, str(area), "iv")
            else:
                logger.info(f"All areas completed.")
            loops = 0
            if SC == 5:
                setpoint -= 0.025
                setpoint = round(setpoint,3)
                changeSetpoint(setpoint)
                SC = 0
                logger.info(f"Setpoint decreased to {setpoint} after 5 short circuits in a row.")
        elif result == "OC":
            OC += 1
            SC = 0
            if loops == 200:
                logger.info(f"Area {area} has completed 200 loops. Moving to next area")
                area += 1
                if area < len(coords):
                    moveToLocation(coords[area])
                    updateDirectory(baseDir, str(area), "iv")
                else:
                    logger.info(f"All areas completed.")
                loops = 0
            if OC == 5:
                setpoint += 0.025
                setpoint = round(setpoint,3)
                changeSetpoint(setpoint)
                OC = 0
                logger.info(f"Setpoint increased to {setpoint} after 5 open circuits in a row.")
        elif result == "MC":
            SC = 0
            OC = 0
            if loops == 200:
                logger.info(f"Area {area} has completed 200 loops. Moving to next area")
                area += 1
                if area < len(coords):
                    moveToLocation(coords[area])
                    updateDirectory(baseDir, str(area), "iv")
                else:
                    logger.info(f"All areas completed.")
                loops = 0
             
except KeyboardInterrupt:
    logger.info(f"Process interrupted by user. Measured up to area {area}.")
