import time
import os, sys
import debug
from lastversion import lastversion
from packaging import version

class UpdateChecker(object):
    def __init__(self,data,scheduler):
        self.workingDir = os.getcwd()
        self.versionFile = os.path.join(self.workingDir,'VERSION')
        self.data = data
        self.version = ""

        #Get installed version by reading VERSION file located in cwd
        if os.path.exists(self.versionFile):
            try:
                with open(self.versionFile) as versionFile:
                    self.version = versionFile.read().strip()
            except OSError:
                debug.error("Unable to open {}".format(self.versionFile))
        else:
            debug.error("File {} does not exist.".format(self.versionFile))

        if self.version != "":
            self.CheckForUpdate()

            # Do a daily check @ 3AM
            scheduler.add_job(self.CheckForUpdate, 'cron', hour=3,minute=0)
            #Check every 5 mins for testing only
            #scheduler.add_job(self.CheckForUpdate, 'cron', minute='*/5')

    def CheckForUpdate(self):
        debug.info("Checking for new release for {} repo installed in {}".format(self.data.UpdateRepo,self.workingDir))

        # Use lastversion to check against github latest release repo, don't look at pre releases
        latest_version = lastversion.latest(self.data.UpdateRepo, output_format='version', pre_ok=False)
        if latest_version != None:
            if latest_version > version.parse(self.version):
                debug.info("New release v{} available.".format(latest_version))
                self.data.newUpdate = True
            else:
                debug.info("No new release.")
                self.data.newUpdate = False
        else:
            debug.error("Unable to get latest version from github, is it tagged properly?")
            

        
        