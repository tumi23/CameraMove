from __future__ import print_function

import logging
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime

import gphoto2 as gp
import piexif
import PIL.Image
from PIL import Image

from importPhotos import Ui_Dialog
from PyQt5 import QtCore, QtGui, QtWidgets

#regex variables
wordRegex = r"([^\s]+)"
nameRegex = r"([^\s]+[(])"
numberRegex = r"([+]\d{1,}|[-]\d{1,})"

# ?? variables
projectName = 'NoName'
saveLocations = []

# Options Variables
imageDelCam = True
imageDelLocal = False
haveCamFolder = True

# Directory Variables
PHOTO_DIR = os.path.expanduser('~/Pictures/from_camera')
TEMPORARY_DIR = os.path.expanduser('~/Pictures/from_camera/NameCheck')
NET_DIR = '/Test'

class importPhotos(Ui_Dialog):
    def __init__(self, dialog):
        Ui_Dialog.__init__(self)
        self.setupUi(dialog)

        self.changeName.clicked.connect(self.changeProjectName)
        self.importButton.clicked.connect(self.import_all_photos_from_cameras)
        self.deleteButton.clicked.connect(self.clear_photos_from_camera)
        self.deleteImagesCheckbox.clicked.connect(self.change_del_camera)
        self.createCamFolderCheckbox.clicked.connect(self.change_create_cam_folder)
        self.regexButton.clicked.connect(self.import_regex_photos_from_cameras)
        self.isoButton.clicked.connect(self.change_iso_setting)

    def change_iso_setting(self):
        camera = gp.check_result(gp.gp_camera_new())
        gp.check_result(gp.gp_camera_init(camera))
        camera_config = gp.check_result(
            gp.gp_camera_get_config(camera))
        for child in gp.check_result(gp.gp_widget_get_children(camera_config)):
            print(gp.check_result(gp.gp_widget_get_label(child)))
        gp.check_result(gp.gp_camera_exit(camera))

    def change_del_camera(self):
        global imageDelCam
        if self.deleteImagesCheckbox.isChecked():
            imageDelCam = True
        else:
            imageDelCam = False

    def change_create_cam_folder(self):
        global haveCamFolder
        if self.createCamFolderCheckbox.isChecked():
            haveCamFolder = True
        else:
            haveCamFolder = False

    def get_target_dir(self, timestamp):
        return os.path.join(PHOTO_DIR, timestamp.strftime('%Y/%d_%m_%Y/'))

    def check_if_project_exists(self, projectName):
        timestamp = datetime.now()
        dest_dir = self.get_target_dir(timestamp)
        dest_dir = os.path.join(dest_dir, projectName)
        if os.path.isdir(dest_dir):
            return False
        else:
            return True

    def check_if_projects_exist(self, txt):
        matches = re.finditer(wordRegex, txt, re.MULTILINE)
        # Find All Scripts
        for matchNum, match in enumerate(matches):
            nameMatches = re.finditer(nameRegex, match.group(), re.MULTILINE)
            # Find Project Name
            for nameMatchNum, nameMatch in enumerate(nameMatches):
                currName = nameMatch.group().replace('(','')
                if not self.check_if_project_exists(currName):
                    return False
        return True

    def changeProjectName(self):
        global projectName
        txt = self.nameEdit.text()
        if len(txt) != 0:
            if self.check_if_project_exists(txt):
                self.currentNameLabel.setText(txt)
                projectName = txt
                self.projectErrorLabel.setText('Name Changed!')
            else:
                self.projectErrorLabel.setText('Project already exists, please pick a new name')
        else:
            self.projectErrorLabel.setText('Name field is empty')
    
    def clear_photos_from_camera(self):
        cameraCounter = 1
        camera_list = []
        # Get list of all connected cameras
        for name, addr in gp.check_result(gp.gp_camera_autodetect()):
            camera_list.append((name, addr))
        if not camera_list:
            self.deletePhotosLabel.setText('No camera detected')
            return 1
        # Sort the camera list
        camera_list.sort(key=lambda x: x[0])
        for item in camera_list:
            cameraPercentage = int((cameraCounter/len(camera_list))*100)
            self.cameraProgressBarDelete.setValue(cameraPercentage)
            self.deletePhotosLabel.setText('Deleting from camera %i of %i' % (cameraCounter, len(camera_list)))
            # initialise camera
            name, addr = item
            camera = gp.Camera()
            # search ports for camera port name
            port_info_list = gp.PortInfoList()
            port_info_list.load()
            idx = port_info_list.lookup_path(addr)
            camera.set_port_info(port_info_list[idx])
            camera.init()
            # Get list of all files from the camera
            camera_files = self.list_camera_files(camera)
            if not camera_files:
                self.deletePhotosLabel.setText('No files found')
            # Deleting files
            counter = 1
            for path in camera_files:
                filePercentage = int((counter/len(camera_files))*100)
                self.fileProgressBarDelete.setValue(filePercentage)
                # Get folder and name from path
                folder, name = os.path.split(path)
                # Delete image from camera
                gp.check_result(gp.gp_camera_file_delete(camera, folder, name))
                counter += 1
            gp.check_result(gp.gp_camera_exit(camera))
            cameraCounter += 1
        self.deletePhotosLabel.setText('Deletion Completed')

    def import_regex_photos_from_cameras(self):
        global haveCamFolder
        computer_files = self.list_computer_files()
        cameraCounter = 1
        camera_list = []
        regexProject = ''
        # Check if projects exist
        txt = self.regexEdit.toPlainText()
        if len(txt) != 0:
            if not self.check_if_projects_exist(txt):
                self.projectRegexErrorLabel.setText('Error: One of those projects exists!')
            else:
                regexProject = txt
        else:
            self.projectRegexErrorLabel.setText('Error: No Text In Text Box!')
            return 1
        # Get list of all connected cameras
        for name, addr in gp.check_result(gp.gp_camera_autodetect()):
            camera_list.append((name, addr))
        if not camera_list:
            self.importPhotosLabel.setText('Error: No camera detected')
            return 1
        # Sort the camera list
        camera_list.sort(key=lambda x: x[0])
        for item in camera_list:
            fileCounter = 1
            cameraPercentage = int((cameraCounter/len(camera_list))*100)
            self.cameraProgressBarRegex.setValue(cameraPercentage)
            self.projectRegexErrorLabel.setText('Copying from camera %i of %i' % (cameraCounter, len(camera_list)))
            # intialize cameraName
            cameraName = 'NoName'
            # initialise camera
            name, addr = item
            camera = gp.Camera()
            # search ports for camera port name
            port_info_list = gp.PortInfoList()
            port_info_list.load()
            idx = port_info_list.lookup_path(addr)
            camera.set_port_info(port_info_list[idx])
            camera.init()
            # Get list of all files from the camera
            camera_files = self.list_camera_files(camera)
            if not camera_files:
                self.importPhotosLabel.setText('No files found')
                return 1
            # Figure out the name of the camera
            for path in camera_files:
                # Find the name of the file from its original path
                folder, name = os.path.split(path)
                # Creating the destination folder for the temporary file
                dest = os.path.join(TEMPORARY_DIR, name)
                if not os.path.isdir(TEMPORARY_DIR):
                    os.makedirs(TEMPORARY_DIR)
                # Load in the file and copy it on to the host machine
                camera_file = gp.check_result(gp.gp_camera_file_get(
                    camera, folder, name, gp.GP_FILE_TYPE_NORMAL))
                gp.check_result(gp.gp_file_save(camera_file, dest))
                # See if the exif info includes any name to attach to this camera.
                exif_dict = piexif.load(dest)
                if len(exif_dict["0th"][piexif.ImageIFD.Artist]) != 0:
                    cameraName = exif_dict["0th"][piexif.ImageIFD.Artist]
                    os.remove(dest)
                    os.rmdir(TEMPORARY_DIR)
                    break
                os.remove(dest)
            currIndex = 0
            timestamp = datetime.now()
            time_dir = self.get_target_dir(timestamp)
            matches = re.finditer(wordRegex, regexProject, re.MULTILINE)
            # Find All Scripts
            for matchNum, match in enumerate(matches):
                currWord = match.group()
                nameMatches = re.finditer(nameRegex, match.group(), re.MULTILINE)
                # Find Project Name
                for nameMatchNum, nameMatch in enumerate(nameMatches):
                    currName = nameMatch.group().replace('(','')
                    project_dir = os.path.join(time_dir, currName)
                    numberMatches = re.finditer(numberRegex, currWord, re.MULTILINE)
                    # Figure out what to delete and import
                    for numberMatchNum, numberMatch in enumerate(numberMatches):
                        currNumber = numberMatch.group()
                        # Needs to be imported
                        if currNumber[0] == '+':
                            currNumber = int(numberMatch.group().replace('+',''))
                            for x in range(currNumber):
                                filePercentage = int((fileCounter/len(camera_files))*100)
                                self.fileProgressBarRegex.setValue(filePercentage)
                                self.projectRegexErrorLabel.setText('Copying from camera %i of %i' % (cameraCounter, len(camera_list)))
                                folder, name = os.path.split(camera_files[currIndex])
                                if haveCamFolder:
                                    dest_dir = os.path.join(project_dir, str(cameraName, 'utf-8'))
                                else:
                                    dest_dir = project_dir
                                # Create directory
                                dest = os.path.join(dest_dir, name)
                                if dest in computer_files:
                                    continue
                                if not os.path.isdir(dest_dir):
                                    os.makedirs(dest_dir)
                                # Import photo
                                camera_file = gp.check_result(gp.gp_camera_file_get(
                                    camera, folder, name, gp.GP_FILE_TYPE_NORMAL))
                                gp.check_result(gp.gp_file_save(camera_file, dest))
                                if imageDelCam:
                                    gp.check_result(gp.gp_camera_file_delete(camera, folder, name))
                                saveLocations.append(dest_dir)
                                currIndex += 1
                        # Needs to be deleted
                        elif currNumber[0] == '-':
                            currNumber = int(numberMatch.group().replace('-',''))
                            for x in range(currNumber):
                                filePercentage = int((fileCounter/len(camera_files))*100)
                                self.fileProgressBarRegex.setValue(filePercentage)
                                self.projectRegexErrorLabel.setText('Copying from camera %i of %i' % (cameraCounter, len(camera_list)))
                                folder, name = os.path.split(camera_files[currIndex])
                                gp.check_result(gp.gp_camera_file_delete(camera, folder, name))
                                currIndex += 1
                        fileCounter += 1
            gp.check_result(gp.gp_camera_exit(camera))
            cameraCounter += 1
            camera.exit()
        self.projectRegexErrorLabel.setText('Import Complete!')

    def import_all_photos_from_cameras(self):
        global haveCamFolder
        computer_files = self.list_computer_files()
        cameraCounter = 1
        camera_list = []
        # Get list of all connected cameras
        for name, addr in gp.check_result(gp.gp_camera_autodetect()):
            camera_list.append((name, addr))
        if not camera_list:
            self.importPhotosLabel.setText('No camera detected')
            return 1
        # Sort the camera list
        camera_list.sort(key=lambda x: x[0])
        for item in camera_list:
            cameraPercentage = int((cameraCounter/len(camera_list))*100)
            self.cameraProgressBarImport.setValue(cameraPercentage)
            self.importPhotosLabel.setText('Copying from camera %i of %i' % (cameraCounter, len(camera_list)))
            # intialize cameraName
            cameraName = 'NoName'
            # initialise camera
            name, addr = item
            camera = gp.Camera()
            # search ports for camera port name
            port_info_list = gp.PortInfoList()
            port_info_list.load()
            idx = port_info_list.lookup_path(addr)
            camera.set_port_info(port_info_list[idx])
            camera.init()
            # Get list of all files from the camera
            camera_files = self.list_camera_files(camera)
            if not camera_files:
                self.importPhotosLabel.setText('No files found')
                return 1
            # Figure out the name of the camera
            for path in camera_files:
                # Find the name of the file from its original path
                folder, name = os.path.split(path)
                # Creating the destination folder for the temporary file
                dest = os.path.join(TEMPORARY_DIR, name)
                if not os.path.isdir(TEMPORARY_DIR):
                    os.makedirs(TEMPORARY_DIR)
                # Load in the file and copy it on to the host machine
                camera_file = gp.check_result(gp.gp_camera_file_get(
                    camera, folder, name, gp.GP_FILE_TYPE_NORMAL))
                gp.check_result(gp.gp_file_save(camera_file, dest))
                # See if the exif info includes any name to attach to this camera.
                exif_dict = piexif.load(dest)
                if len(exif_dict["0th"][piexif.ImageIFD.Artist]) != 0:
                    cameraName = exif_dict["0th"][piexif.ImageIFD.Artist]
                    os.remove(dest)
                    os.rmdir(TEMPORARY_DIR)
                    break
                os.remove(dest)
            counter = 1
            # Old Import Part
            for path in camera_files:
                filePercentage = int((counter/len(camera_files))*100) 
                self.fileProgressBarImport.setValue(filePercentage)
                # Construct the path that the images will be copied into on the host machine
                timestamp = datetime.now()
                folder, name = os.path.split(path)
                dest_dir = self.get_target_dir(timestamp)
                dest_dir = os.path.join(dest_dir, projectName)
                if haveCamFolder:
                    dest_dir = os.path.join(dest_dir, str(cameraName, 'utf-8'))
                dest = os.path.join(dest_dir, name)
                if dest in computer_files:
                    continue
                if not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)
                
                # Save image from camera
                camera_file = gp.check_result(gp.gp_camera_file_get(
                    camera, folder, name, gp.GP_FILE_TYPE_NORMAL))
                gp.check_result(gp.gp_file_save(camera_file, dest))
                saveLocations.append(dest)
                # Delete image from camera
                if imageDelCam:
                    gp.check_result(gp.gp_camera_file_delete(camera, folder, name))
                
                counter += 1
            gp.check_result(gp.gp_camera_exit(camera))
            cameraCounter += 1
            camera.exit()
        self.importPhotosLabel.setText('Import Complete!')

    def list_computer_files(self):
        result = []
        for root, dirs, files in os.walk(os.path.expanduser(PHOTO_DIR)):
            for name in files:
                if '.thumbs' in dirs:
                    dirs.remove('.thumbs')
                if name in ('.directory',):
                    continue
                ext = os.path.splitext(name)[1].lower()
                if ext in ('.db',):
                    continue
                result.append(os.path.join(root, name))
        return result

    def list_camera_files(self,camera, path='/'):
        result = []
        # get files
        gp_list = gp.check_result(
            gp.gp_camera_folder_list_files(camera, path))
        for name, value in gp_list:
            result.append(os.path.join(path, name))
        # read folders
        folders = []
        gp_list = gp.check_result(
            gp.gp_camera_folder_list_folders(camera, path))
        for name, value in gp_list:
            folders.append(name)
        # recurse over subfolders
        for name in folders:
            result.extend(self.list_camera_files(camera, os.path.join(path, name)))
        return result

    def get_camera_file_info(self,camera, path):
        folder, name = os.path.split(path)
        return gp.check_result(
            gp.gp_camera_file_get_info(camera, folder, name))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    dialog = QtWidgets.QDialog()

    prog = importPhotos(dialog)

    dialog.show()
    sys.exit(app.exec_())
