import subprocess, re
import pandas as pd
from pathlib import Path
    
class phreeqcModel():
    def __init__(self):
        self.phBin = ""
        self.phDb = ""
        self.inputFile = ""
        self.outputFile = ""
        self.simList = []
        self.breakers = []
        self.outDict = {}
        self.dfNames = []
        self.dfDict = {}
        
    def runModel(self):
        # Ensure we pass proper string paths and run in the directory of the input file
        input_path = Path(str(self.inputFile)).resolve()
        output_path = Path(str(self.outputFile)).resolve()
        db_path = Path(str(self.phDb)).resolve()
        bin_path = Path(str(self.phBin)).resolve()
        cwd = input_path.parent

        cmd = [str(bin_path), str(input_path), str(output_path), str(db_path)]
        phProc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(cwd),
            text=True,
        )

        # Stream stderr for visibility
        if phProc.stderr is not None:
            for line in phProc.stderr:
                print(line.rstrip())
        ret = phProc.wait()
        if ret != 0:
            raise RuntimeError(f"PHREEQC exited with code {ret}. Command: {' '.join(cmd)}")
        
    def showSimulations(self,file=None):
        if file==None:
            file = self.outputFile
        outLines = open(file).readlines()
        self.outlines = outLines
        
        Id = 1
        for index,line in enumerate(outLines):
            if line.startswith("Reading input data for simulation"):
                simDict = {}
                simDict["Id"] = Id
                Id+=1
                simDict["Begin"] = index
                for index2, line2 in enumerate(outLines[index:]):
                    if line2 == "TITLE\n":
                        simDict["Title"] =  outLines[index+index2+3][:-1]
                    if line2 == "End of simulation.\n":
                        simDict["End"] = index2 + index + 1
                        break
                if "Title" in simDict.keys():
                    self.simList.append(simDict)
        
        print("Parsing output file: %d simulations found"%len(self.simList))
        for item in self.simList:
            print("Simulation %d: %s from line %d to %d "%(item["Id"],item["Title"],item["Begin"],item["End"]))
    
    #----------------------------------------------------------
    def getSimulation(self, Id):
        
        begInitS = "Beginning of initial solution calculations"
        endOfSim = 'End of simulation.'
        begBatch = 'Beginning of batch-reaction calculations.'

        for item in self.simList:
            if item["Id"] == Id:
                global simLines 
                simLines = self.outlines[item["Begin"]:item["End"]] 

        outDict ={
            'initialSolution':{
                'Exists':False
            },
            'batchReaction':{
                'Exists':False,
                'Step':0,
                'stepDictList':[]
            }
        }

        for index, line in enumerate(simLines):
            if line.startswith(begInitS):
                outDict['initialSolution']['Exists'] = True
                outDict['initialSolution']['Start'] = index
                for index2, line2 in enumerate(simLines[index:]):
                    if line2.startswith((endOfSim, begBatch)):
                        outDict['initialSolution']['End'] = index2+index
                        break
            elif line.startswith(begBatch):
                outDict['batchReaction']['Exists'] = True
            elif line.startswith("Reaction step"):
                outDict['batchReaction']['Step'] += 1
                for index2, line2 in enumerate(simLines[index+1:]):                    
                    if line2.startswith(('Reaction step',endOfSim)):
                        batchDict={
                            'Number': outDict['batchReaction']['Step'],
                            'Start': index,
                            'End': index+index2+1
                        }
                        break
                outDict['batchReaction']['stepDictList'].append(batchDict)

        print('''Simulation content:
        Initial solution calculation: %s
        Batch reaction calculations: %s'''%(str(outDict['initialSolution']['Exists']),str(outDict['batchReaction']['Exists'])))
        if outDict['batchReaction']:
            print('        Number of reactions steps: %d'%outDict['batchReaction']['Step'])

        #self.outDict = outDict
        #self.simLines = simLines
        
        def parseCalcLines(calcLines):
            
            calcBreakers = {
                "phaseAssemblage":{
                    'Headers':['Phase','SI','log IAP','log K(T, P)','Initial Moles','Final Moles','Delta Moles'],
                    'numericHeaders':['SI','log IAP','log K(T, P)','Initial Moles','Final Moles','Delta Moles']},
                "solutionComposition":{
                    'Headers':['Elements','Molality','Moles','Description'],
                    'numericHeaders':['Molality','Moles']},
                "descriptionSolution":{
                    'Headers':['Parameter','Value'],
                    'numericHeaders':['Value']},
                "redoxCouples":{
                    'Headers':['Redox couple','pe','Eh(volts)'],
                    'numericHeaders':['pe','Eh(volts)']},
                "distributionSpecies":{
                    'Headers':['Species','Molality','Activity','Log Molality','Log Activity','Log Gamma','mole V cm3/mol'],
                    'numericHeaders':['Molality','Activity','Log Molality','Log Activity','Log Gamma','mole V cm3/mol']},
                "saturationIndices":{
                    'Headers':['Phase','SI','log IAP','log K(298 K,   1 atm)','Description'],
                    'numericHeaders':['SI','log IAP','log K(298 K,   1 atm)']},
            }
            
            dfDict = {}
            
            def findEnd(index,calcLines,afterHeaders):
                finalIndex = None
                for index2, line2 in enumerate(calcLines[index+afterHeaders:]): 
                    if line2 == '\n':
                        finalIndex = index + afterHeaders + index2
                        break
                return finalIndex
            #insert solution that finds end as ----string---
            for index,line in enumerate(calcLines):
                if re.search("Phase assemblage",line):
                    calcBreakers["phaseAssemblage"]["Start"]=index+5
                    calcBreakers["phaseAssemblage"]["End"]=findEnd(index,calcLines,5)
                elif re.search("Solution composition",line):
                    calcBreakers["solutionComposition"]["Start"]=index+4
                    calcBreakers["solutionComposition"]["End"]=findEnd(index,calcLines,4)
                elif re.search("Description of solution",line):
                    calcBreakers["descriptionSolution"]["Start"]=index+2
                    calcBreakers["descriptionSolution"]["End"]=findEnd(index,calcLines,2)
                elif re.search("Redox couples",line):
                    calcBreakers["redoxCouples"]["Start"]=index+4
                    calcBreakers["redoxCouples"]["End"]=findEnd(index,calcLines,4)
                elif re.search("Distribution of species",line):
                    calcBreakers["distributionSpecies"]["Start"]=index+6
                    calcBreakers["distributionSpecies"]["End"]=findEnd(index,calcLines,6)
                elif re.search("Saturation indices",line):
                    calcBreakers["saturationIndices"]["Start"]=index+4
                    calcBreakers["saturationIndices"]["End"]=findEnd(index,calcLines,4)
          
            for key in calcBreakers.keys():
                tempDict = calcBreakers[key]
                if 'Start' in tempDict:
                    filterLines = []
                    breakLines = calcLines[tempDict['Start']:tempDict['End']]
                    for line in breakLines:
                        line = line.strip()
                        line = re.sub('=','',line)
                        line = re.sub(',  [0-9]',', [0-9]',line)
                        line = re.sub('is reactant','%% %%',line)
                        line = re.sub('\s{2,}','%%',line)
                        line = line.split('%%')[:len(tempDict['Headers'])]
                        noneList = [None for i in range(len(tempDict['Headers']))]
                        noneList[:len(line)] = line
                        filterLines.append(noneList)
                    calcDf = pd.DataFrame(filterLines,columns=tempDict['Headers'])
                    calcDf = calcDf.set_index(tempDict['Headers'][0])
                    for header in tempDict['numericHeaders']:
                        calcDf[header] = calcDf[header].apply(pd.to_numeric, errors='coerce')
                    dfDict[key] = calcDf
                
            return dfDict

        class phreeqcSimulation():
            def getSimulationDict(self):
                print(outDict)
            def getInitialSolution(self):
                if outDict['initialSolution']['Exists']:
                    start = outDict['initialSolution']['Start']
                    end = outDict['initialSolution']['End']
                    initSolLines = simLines[start:end]
                    calcDict = parseCalcLines(initSolLines)
                    return calcDict
            def getBatchReaction(self,number):
                if outDict['batchReaction']['Exists']:
                    for item in outDict['batchReaction']['stepDictList']:
                        if item['Number'] == number:
                            start = item['Start']
                            end = item['End']
                            break
                    initSolLines = simLines[start:end]
                    calcDict = parseCalcLines(initSolLines)
                    return calcDict
        
        return phreeqcSimulation()

                     
        
    def parseResults(self,file=None):
        if file==None:
            file = self.outputFile
            
        outLines = open(file).readlines()
        
        #getting breakers
        for index,line in enumerate(outLines):
            match = re.search('(\-)+.+[A-Z]+.+[a-z]+(\-)+$',line)
            if match != None:
                self.breakers.append(index)
                name = re.sub('-| ','',line[:-1])
                self.dfNames.append(name)
        self.dfNames.append(len(outLines))
        #getting df
        for index,name in enumerate(self.dfNames):
            dfText = open(self.outputFile).readlines()[self.breakers[index]+2:self.breakers[index+1]-1]
            print(dfText)
    
    
        
        print(self.dfnames)



