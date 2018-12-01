#!python3
# -*- coding: utf-8 -*-
"""
Created on Fri Apr 28 12:49:24 2017
# Hypervisor - Virtualización
@author: Cristian Vázquez Cordero
"""

from __future__ import print_function
import atexit
import requests
import sys
import ssl
import ctypes  # Tomar información del sistema
import time
import json
from pyVim import connect
from pyVmomi import vmodl
from pyVmomi import vim
from tools import tasks
from PyQt5 import uic, QtGui, QtCore
from PyQt5.QtWidgets import *
import platform


requests.packages.urllib3.disable_warnings()

vms = []
service_instance = ""
datastores = []


class AboutMeWindow(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        uic.loadUi("gui/autor.ui", self)
        self.setWindowTitle("Acerca de")


class EsxiInfoDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        uic.loadUi("gui/esxiInfo.ui", self)
        self.exitButton.clicked.connect(self.exit)
        self.getInformation()

    def getInformation(self):
        self.esxi=getEsxiInfo()
        self.marcaBox.insert(self.esxi.hardware.vendor)
        self.modeloBox.insert(self.esxi.hardware.model)
        self.uuidBox.insert(self.esxi.hardware.uuid)
        self.procBox.insert(self.esxi.hardware.cpuModel)
        self.ncoresBox.insert(str(self.esxi.hardware.numCpuCores))
        self.nhilosBox.insert(str(self.esxi.hardware.numCpuThreads))
        self.nicBox.insert(str(self.esxi.hardware.numNics))
        self.freqBox.insert(str(self.esxi.hardware.cpuMhz)+ " Mhz")
        MBFACTOR =float(1 << 20)
        memoryCapacityInMB=float("{0:.2f}".format(self.esxi.hardware.memorySize/MBFACTOR/1024))
        self.memtotalBox.insert(str(memoryCapacityInMB)+" GB")
        memoryUsage=float("{0:.2f}".format(self.esxi.quickStats.overallMemoryUsage/1024))
        self.memusoBox.insert(str(memoryUsage)+" GB")
        memLibre=100 - ((float(memoryUsage) / memoryCapacityInMB) * 100)
        memLibre=float("{0:.2f}".format(memLibre))
        self.memlibreBox.insert(str(memLibre)+ " %")

        self.nombresoBox.insert(str(self.esxi.config.name))
        self.versionBox.insert(str(self.esxi.config.product.fullName))
        self.fechaBox.insert(str(self.esxi.runtime.bootTime))
        vMotion=str(self.esxi.config.vmotionEnabled)
        faultTolerance=str(self.esxi.config.faultToleranceEnabled)
        if (vMotion=="False"):
            self.vmotionBox.insert("Desactivado")
        else:
            self.vmotionBox.insert("Activado")
        if (faultTolerance == "False"):
            self.toleranciaBox.insert("Desactivado")
        else:
            self.toleranciaBox.insert("Activado")


        #print("\nInformacion: \n {0}".format(self.esxi))

    def exit(self):
        self.close()

class RenameVmWindow(QDialog):
    def __init__(self, ventana):
        QDialog.__init__(self)
        self._ventana=ventana
        uic.loadUi("gui/newName.ui", self)
        self.setWindowTitle("Renombrar máquina virtual")
        self.exitButton.clicked.connect(self.exit)
        self.renameButton.clicked.connect(self.renombrar)
    def renombrar(self):
        fila = self._ventana.mvTable.currentRow()
        if (fila != -1):
            obj = self._ventana.mvTable.item(fila, 1)
            uid = obj.text()
            try:
                VM = service_instance.content.searchIndex.FindByUuid(None, uid, True, True)  # Objeto a borrar
                new_name=self.nombreBox.text()
                if (new_name.isalpha and new_name!=""):
                    TASK = VM.Rename(new_name)
                    tasks.wait_for_tasks(service_instance, [TASK])
                    self._ventana.refreshWindow()
                    #print("{0}".format(TASK.info.state))
                    self.exit()
                    try:
                        _correctdialog = CorrectDialog()
                        _correctdialog.exec_()
                    except:
                        pass
                else:
                    self._errorConexion = ErrorDialog()
                    self._errorConexion.lineEdit.setPlainText("Nombre introducido no es alfanumérico. ")
                    self._errorConexion.exec_()
            except:
                self._errorConexion = ErrorDialog()
                self._errorConexion.lineEdit.setPlainText("Error al buscar {0}. ".format(uid))
                self._errorConexion.exec_()

    def exit(self):
        self.close()


class NewVmWindow(QDialog):
    def __init__(self,ventana):
        QDialog.__init__(self)
        self._ventana=ventana
        uic.loadUi("gui/newVm.ui", self)
        self.setWindowTitle("Crear nueva máquina virtual")
        self.exitButton.clicked.connect(self.salir)
        self.crearButton.clicked.connect(self.createVm)
        try:
            numProcs = getEsxiInfo().hardware.numCpuCores;
            for i in range(numProcs):
                i+=1
                self.procsBox.addItem(str(i))
        except:
            self.procsBox.addItem("1")
        self.datastoreBox.addItems(getDatastoresName())

        self.vm_soText = [self.soBox.itemText(i) for i in range(self.soBox.count())]
        with open('so.json') as f:
            self.mapa = json.load(f)

        # self.vm_soGuestId = ["asianux3_64Guest","asianux3Guest", "asianux4_64Guest","asianux4Guest","centos64Guest","centosGuest","darwin10_64Guest","darwin10Guest",
        #                 "darwin11_64Guest","darwin11Guest","darwin12_64Guest","darwin13_64Guest","darwin64Guest","darwinGuest","debian4_64Guest", "debian4Guest",
        #                 "debian5_64Guest","debian5Guest","debian6_64Guest","debian6Guest","debian7_64Guest","debian7Guest","dosGuest","eComStation2Guest","eComStationGuest",
        #                 "fedora64Guest","fedoraGuest","freebsd64Guest","freebsdGuest","genericLinuxGuest","mandrakeGuest","mandriva64Guest","mandrivaGuest","netware4Guest",
        #                 "netware5Guest","netware6Guest","nld9Guest","oesGuest","openServer5Guest","openServer6Guest","opensuse64Guest","opensuseGuest","oracleLinux64Guest",
        #                 "oracleLinuxGuest","os2Guest","other24xLinux64Guest","other24xLinuxGuest","other26xLinux64Guest","other26xLinuxGuest","other3xLinux64Guest","other3xLinuxGuest",
        #                 "otherGuest","otherGuest64","otherLinux64Guest","otherLinuxGuest","redhatGuest","rhel2Guest","rhel3_64Guest","rhel3Guest","rhel4_64Guest","rhel4Guest",
        #                 "rhel5_64Guest","rhel5Guest","rhel6_64Guest","rhel6Guest","rhel7_64Guest","rhel7Guest","sjdsGuest","sles10_64Guest","sles10Guest","sles11_64Guest","sles11Guest",
        #                 "sles12_64Guest","sles12Guest","sles64Guest","slesGuest","solaris10_64Guest","solaris10Guest","solaris11_64Guest","solaris6Guest","solaris7Guest","solaris8Guest",
        #                 "solaris9Guest","suse64Guest","suseGuest","turboLinux64Guest","turboLinuxGuest","ubuntu64Guest","ubuntuGuest","unixWare7Guest","vmkernel5Guest","vmkernelGuest",
        #                 "win2000AdvServGuest","win2000ProGuest","win2000ServGuest","win31Guest","win95Guest","win98Guest","windows7_64Guest","windows7Guest","windows7Server64Guest",
        #                 "windows8_64Guest","windows8Guest","windows8Server64Guest","windowsHyperVGuest","winLonghorn64Guest","winLonghornGuest","winMeGuest","winNetBusinessGuest",
        #                 "winNetDatacenter64Guest","winNetDatacenterGuest","winNetEnterprise64Guest","winNetEnterpriseGuest","winNetStandard64Guest","winNetStandardGuest","winNetWebGuest",
        #                 "winNTGuest","winVista64Guest","winVistaGuest","winXPHomeGuest","winXPPro64Guest","winXPProGuest"]
        #
        # self.mapa = dict(zip(self.vm_soText,self.vm_soGuestId))
        # #Guarda informacion
        # with open('so.json', 'w') as fp:
        #     json.dump(self.mapa, fp)

    def createVm(self):
        #Obtener conexion
        content = service_instance.RetrieveContent()
        datacenter = content.rootFolder.childEntity[0]
        vmfolder = datacenter.vmFolder
        hosts = datacenter.hostFolder.childEntity
        resource_pool = hosts[0].resourcePool

        devices = []
        vm_name = self.nombreBox.text()
        datastore = self.datastoreBox.currentText()
        vm_procs = self.procsBox.currentText()
        vm_memoria = self.memBox.text()
        vm_hdd = self.hddBox.text()
        vm_so = self.soBox.currentText()

        #Busqueda del valor. No se puede usar la clave directamente porque
        #algunas claves tienen un espacio al final.
        for c, v in self.mapa.items():
            if (vm_so in c):
                self.vm_soGuestId = v
                break

        #print("Valor de Sistema Operativo: {0}".format(self.vm_soGuestId))

        datastore_path = '[' + datastore + '] ' + vm_name
        vmx_file = vim.vm.FileInfo(logDirectory=None,
                                   snapshotDirectory=None,
                                   suspendDirectory=None,
                                   vmPathName=datastore_path)
        #Comprobaciones de campos
        maxMem = int(getEsxiInfo().hardware.memorySize / 1024 / 1024)
        if (vm_name==""):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Nombre no puede estar vacío. ")
            self._errorConexion.exec_()
        elif (vm_memoria == ""):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Memoria no puede estar vacío. ")
            self._errorConexion.exec_()
        elif (vm_hdd == ""):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Disco duro no puede estar vacío. ")
            self._errorConexion.exec_()
        elif not (vm_name.isalnum()):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Nombre introducido no es alfanumérico. ")
            self._errorConexion.exec_()
        elif not (vm_memoria.isdigit()):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Memoria (MB) no es un número. ")
            self._errorConexion.exec_()
        elif (  (int(float(vm_memoria)) <= 0) or (int(float(vm_memoria) > int(maxMem) ))):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Memoria (MB) debe de ser mayor a 0 (MB) y menor a {0} (MB).".format(maxMem))
            self._errorConexion.exec_()
        elif not (vm_hdd.isdigit()):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Disco duro (GB) no es un número. ")
            self._errorConexion.exec_()
        elif (int(float(vm_hdd)) <= 0):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Disco duro (GB) debe de ser mayor a 0. ")
            self._errorConexion.exec_()
        else:
            try:
                config = vim.vm.ConfigSpec(name=vm_name, memoryMB=int(vm_memoria), numCPUs=int(vm_procs),
                                           files=vmx_file, guestId=self.vm_soGuestId,
                                           version='vmx-09', deviceChange=devices)
                #print("Creating VM %s" % (vm_name))
                task = vmfolder.CreateVM_Task(config=config, pool=resource_pool)
                tasks.wait_for_tasks(service_instance, [task])
                self._ventana.refreshWindow()
                self.close()
                try:
                    _correctdialog = CorrectDialog()
                    _correctdialog.exec_()
                except:
                    pass
            except:
                #print ("Error al crear la MV. ")
                e = sys.exc_info()[0]
                #print(e)
                _errorConexion = ErrorDialog()
                _errorConexion.setWindowTitle("Error al crear la MV.")
                _errorConexion.lineEdit.setPlainText("Error al crear la MV. ".format(e))
                _errorConexion.exec_()
    #Salir
    def salir(self):
        self.close()


class ErrorDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        uic.loadUi("gui/error.ui", self)
        self.setWindowTitle("Error")
        self.buttonBox.clicked.connect(self.salir)
        self.buttonBox.button(QDialogButtonBox.Close).setText("Cerrar ventana")
        self.buttonBox.button(QDialogButtonBox.Close).setMinimumWidth(120);
    #Salir
    def salir(self):
        self.close()


class CorrectDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        uic.loadUi("gui/correcto.ui", self)
        self.correctButton.clicked.connect(self.salir)

    def salir(self):
        self.close()


class VmInfoDialog(QDialog):
    def __init__(self,uid):
        QDialog.__init__(self)
        uic.loadUi("gui/mvInfo.ui", self)
        self.exitButton.clicked.connect(self.salir)
        self.getInformation(uid)

    def getInformation(self,uid):
        # Obtiene el objeto VM actualizado en vms
        self.vm=None
        for i in vms:
            if (i.config.instanceUuid == uid):
                #print(uid)
                self.vm=i
                break
        self.nombreBox.insert(self.vm.config.name)
        self.rutaBox.insert(self.vm.config.vmPathName)
        self.uuidBox.insert(self.vm.config.instanceUuid)
        self.soBox.insert(self.vm.config.guestFullName)
        tools_version = self.vm.guest.toolsStatus
        if (tools_version!="toolsNotInstalled"):
            self.vmtoolsBox.insert("Instalado. Versión: {0}".format(tools_version))
        else:
            self.vmtoolsBox.insert("No instalado")
        self.nicBox.insert(str(self.vm.config.numEthernetCards))
        self.ncoresBox.insert(str(self.vm.config.numCpu))
        self.memtotalBox.insert(str(self.vm.config.memorySizeMB/1024))
        self.hddnBox.insert(str(self.vm.config.numVirtualDisks))
        template=str(self.vm.config.template)
        if (template=="False"):
            self.templateBox.insert("No")
        else:
            self.templateBox.insert("Si")
        if (self.vm.runtime.powerState=="poweredOn"):
            self.fechaBox.insert(str(self.vm.runtime.bootTime))
        else:
            self.fechaBox.insert("Apagada")
        commited = float("{0:.2f}".format(self.vm.storage.committed / 1024/1024/1024))
        uncommited = float("{0:.2f}".format(self.vm.storage.uncommitted / 1024 / 1024 / 1024))
        self.hddusoBox.insert(str(commited)+" GB")
        self.hddasignadoBox.insert(str(uncommited) + " GB")
        #print("getInformation "+ str(self.vm))
    #Salir boton
    def salir(self):
        self.close()


class AskDialog(QDialog):
    def __init__(self,text):
        QDialog.__init__(self)
        uic.loadUi("gui/askyn.ui", self)
        self.lineEdit.setPlainText(text)
        self.cancelButton.clicked.connect(self.salir)
        self.acceptButton.clicked.connect(self.aceptar)
    #Aceptar boton
    def aceptar(self):
        self.accept()
        self.close()
    #Salir boton
    def salir(self):
        self.reject()
        self.close()


# Clase MAIN heredada de QMainWindow (Constructor de ventanas)
class HypervisorMainWindow(QMainWindow):
    def __init__(self):
        # Iniciar el objeto QMainWindow
        QMainWindow.__init__(self)
        # Cargar la configuración del archivo .ui en el objeto
        uic.loadUi("gui/gui6.ui", self)
        self.setWindowTitle("Virtualización - Hypervisor de Cristian")
        self.setMinimumSize(670, 585)
        self.setMaximumSize(1920, 1080)
        # Centrar y mover
        if (platform.system() == "Windows"):
            resolucion = ctypes.windll.user32
            resolucion_ancho = resolucion.GetSystemMetrics(0)
            resolucion_alto = resolucion.GetSystemMetrics(1)
        else:
            resolucion_ancho = 800
            resolucion_alto = 600
        left = (resolucion_ancho / 2) - (self.frameSize().width() / 2)
        top = (resolucion_alto / 2) - (self.frameSize().height() / 2)
        self.move(left, top)
        self.actionAutor.setShortcut('Ctrl+A')
        self.actionAutor.triggered.connect(self.aboutMe)

        #Botones
        self.connectButton.setFlat(True)
        self.connectButton.clicked.connect(self.connectToEsxi)

        self.crearButton.clicked.connect(self.createNewVm)
        self.actionCrear_nueva_m_quina_virtual.triggered.connect(self.createNewVm)
        self.powerButton.clicked.connect(self.powerVm)
        self.actionApagar_Encender_m_quina_virtual.triggered.connect(self.powerVm)
        self.deleteButton.clicked.connect(self.deleteVm)
        self.actionBorrar_m_quina_virtual.triggered.connect(self.deleteVm)
        self.rebootButton.clicked.connect(self.rebootVm)
        self.actionReiniciar_m_quina_virtual.triggered.connect(self.rebootVm)
        self.renameButton.clicked.connect(self.renameVm)
        self.actionRenombrar_m_quina_virtual.triggered.connect(self.renameVm)
        self.infoButton.clicked.connect(self.infoVm)
        self.actionInformaci_n.triggered.connect(self.infoVm)
        self.actionSalir.triggered.connect(self.exit)

        self.urlAction.returnPressed.connect(self.connectButton.click)
        self.passAction.returnPressed.connect(self.connectButton.click)
        self.userAction.returnPressed.connect(self.connectButton.click)

        self.refreshButton.clicked.connect(self.refreshWindow)
        self.esxiInfoButton.clicked.connect(self.openEsxiInformation)
        self.actionMostrar_informaci_n_ESXI.triggered.connect(self.openEsxiInformation)

    #Iniciación del entorno
    def startEnvironment(self, mvs, ds):
        # Activar botones y menú
        self.crearButton.setEnabled(True)
        self.actionCrear_nueva_m_quina_virtual.setEnabled(True)
        self.powerButton.setEnabled(True)
        self.actionApagar_Encender_m_quina_virtual.setEnabled(True)
        self.rebootButton.setEnabled(True)
        self.actionReiniciar_m_quina_virtual.setEnabled(True)
        self.deleteButton.setEnabled(True)
        self.actionBorrar_m_quina_virtual.setEnabled(True)
        self.renameButton.setEnabled(True)
        self.actionRenombrar_m_quina_virtual.setEnabled(True)
        self.infoButton.setEnabled(True)
        self.actionInformaci_n.setEnabled(True)
        self.refreshButton.setEnabled(True)
        self.esxiInfoButton.setEnabled(True)
        self.actionMostrar_informaci_n_ESXI.setEnabled(True)

        # Tabla de MV
        tableMV = self.mvTable
        tableMV.setRowCount(len(mvs))
        # table.setColumnCount(2)

        # Establecer horizontalheader
        headerMV = tableMV.horizontalHeader()
        for i in range(8):
            headerMV.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            # header.setSectionResizeMode(i, QHeaderView.Stretch)

        # Tabla de ds
        tableDS = self.datastoresTable
        tableDS.setRowCount(len(ds))
        headerDS = tableDS.horizontalHeader()
        for i in range(10):
            headerDS.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            # header.setSectionResizeMode(i, QHeaderView.Stretch)

        # Mostrar MV
        cont = 0
        for child in mvs:
            print_vm_info(cont, child, self)
            cont += 1

        # Mostrar DS
        cont = 0
        for d in ds:
            print_datastore_info(cont, self, d)
            cont += 1

        #Mostrar update
        self.update2.setText(time.strftime("%d/%m/%Y - %H:%M:%S"))
        #print(d.summary)

    #Conectar a Host
    def connectToEsxi(self):
        #Obtencion de datos
        url = self.urlAction.text()
        usuario = self.userAction.text()
        password = self.passAction.text()
        #Comprobación de datos
        if (url == ""):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("IP no introducida correctamente. ")
            self._errorConexion.exec_()
        elif (usuario == ""):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Usuario no introducido correctamente. ")
            self._errorConexion.exec_()
        elif (password == ""):
            self._errorConexion = ErrorDialog()
            self._errorConexion.lineEdit.setPlainText("Contraseña no introducida correctamente. ")
            self._errorConexion.exec_()
        else:
            #Conexion
            try:
                #print ("Conectando a: "+url+" con usuario:"+usuario+" y contraseña: "+password)
                global service_instance
                service_instance = connect.SmartConnect(protocol='https',
                                                        host=url,
                                                        user=usuario,
                                                        pwd=password)
                atexit.register(connect.Disconnect, service_instance)
                content = service_instance.RetrieveContent()
                container = content.rootFolder  # Punto de entradas
                viewType = [vim.VirtualMachine]  # Objetos a buscar
                containerView = content.viewManager.CreateContainerView(container, viewType,
                                                                        recursive=True)
                global datastores
                datastores = get_obj(content, [vim.Datastore])
                mvs = containerView.view  # Lista de MV
                self.startEnvironment(mvs, datastores) #Inicio del entorno

            except Exception as e:
                self._errorConexion = ErrorDialog()
                #print(str(e))
                try:
                    if "periodo de tiempo" in (str(e)):
                        self._errorConexion.lineEdit.setPlainText("Error al conectar al servidor: {0} \n{1}".format(url,"-> Se supero el tiempo de espera. Timeout."))
                    elif "incorrect user name or password" in (str(e.msg)):
                        #print (str(e.msg))
                        self._errorConexion.lineEdit.setPlainText("Error al conectar al servidor: {0} \n{1}".format(url,"-> Usuario y/o contraseña incorrectos."))
                    else:
                        self._errorConexion.lineEdit.setPlainText("Error al conectar al servidor: {0} \n ".format(url))
                except:
                    self._errorConexion.lineEdit.setPlainText("Error al conectar al servidor: {0} \n ".format(url))
                self._errorConexion.exec_()

    #Información acerca del ESXI
    def openEsxiInformation(self):
        _ventanaInfoEsxi= EsxiInfoDialog()
        _ventanaInfoEsxi.exec_()

    #Actualizar ventana
    def refreshWindow(self):
        #print("refreshWindows")
        global service_instance
        global datastores
        global vms
        vms = []
        content = service_instance.RetrieveContent()
        container = content.rootFolder
        viewType = [vim.VirtualMachine]
        containerView = content.viewManager.CreateContainerView(container, viewType,recursive=True)
        datastores = get_obj(content, [vim.Datastore])
        mvs = containerView.view  # Lista de MV
        self.startEnvironment(mvs, datastores)


    #Crear Máquina Virtual (lanza ventana)
    def createNewVm(self):
        _ventanaCrearMV = NewVmWindow(self)
        _ventanaCrearMV.exec_()

    #Información acerca de la MV
    def infoVm(self):
        fila = self.mvTable.currentRow()
        if (fila != -1):
            obj = self.mvTable.item(fila, 1)
            uid = obj.text()
            self._vminfodialog = VmInfoDialog(uid)
            self._vminfodialog.exec_()

    #Encender/Apagar máquina virtual
    def powerVm(self):
        fila = self.mvTable.currentRow()
        if (fila != -1):
            obj = self.mvTable.item(fila, 1)
            uid = obj.text()
            try:
                VM = service_instance.content.searchIndex.FindByUuid(None, uid, True, True)  # Objeto a borrar
                if format(VM.runtime.powerState) == "poweredOn": #Encendida
                    #print("MV encendida. Apagando. {0}".format(VM.name))
                    TASK = VM.PowerOffVM_Task()
                    tasks.wait_for_tasks(service_instance, [TASK])
                    self.refreshWindow()
                    #print("{0}".format(TASK.info.state))
                else: #Apagada
                    #print("MV apagada. Encendiendo. {0}".format(VM.name))
                    TASK = VM.PowerOnVM_Task()
                    tasks.wait_for_tasks(service_instance, [TASK])
                    self.refreshWindow()
                    #print("{0}".format(TASK.info.state))
                try:
                    _correctdialog = CorrectDialog()
                    _correctdialog.exec_()
                except:
                    pass
            except Exception as e:
                self.exceptTreatment(e)

    def rebootVm(self):
        fila = self.mvTable.currentRow()
        if fila != -1:
            obj = self.mvTable.item(fila, 1)
            uid = obj.text()
            try:
                VM = service_instance.content.searchIndex.FindByUuid(None, uid, True, True)  # Objeto a borrar
                if format(VM.runtime.powerState) == "poweredOn":
                    #print("MV encendida. Reiniciando. {0}".format(VM.name))
                    TASK = VM.ResetVM_Task()
                    tasks.wait_for_tasks(service_instance, [TASK])
                    self.refreshWindow()
                    try:
                        _correctdialog = CorrectDialog()
                        _correctdialog.exec_()
                    except:
                        pass
            except Exception as e:
                self.exceptTreatment(e)

    def deleteVm(self):
        fila=self.mvTable.currentRow()
        if (fila!=-1):
            try:
                obj=self.mvTable.item(fila,1)
                _askdialog = AskDialog("¿Estás seguro de que desea eliminar \""+self.mvTable.item(fila,0).text()+"\" ?")
                if (_askdialog.exec_()==QDialog.Accepted):
                    uid=obj.text()
                    try:
                        VM = service_instance.content.searchIndex.FindByUuid(None,uid,True,True) #Objeto a borrar
                        if format(VM.runtime.powerState) == "poweredOn":
                            #print("MV encendida. Apagando antes de borrar. {0}".format(VM.name))
                            TASK = VM.PowerOffVM_Task()
                            tasks.wait_for_tasks(service_instance, [TASK])
                            #print("{0}".format(TASK.info.state))
                        TASK = VM.Destroy_Task()
                        tasks.wait_for_tasks(service_instance, [TASK])
                        self.refreshWindow()
                        try:
                            _correctdialog = CorrectDialog()
                            _correctdialog.exec_()
                        except:
                            pass
                    except Exception as e:
                        self.exceptTreatment(e)
            except:
                pass

    def renameVm(self):
        _ventanaRenombrarMV = RenameVmWindow(self)
        _ventanaRenombrarMV.exec_()

    #Submenu Acerca de
    def aboutMe(self):
        _ventanaAutor= AboutMeWindow()
        _ventanaAutor.exec_()

    #Tratamiento de Excepcion PowerOn, Reboot y Rename
    def exceptTreatment(self, e):
        self._errorConexion = ErrorDialog()
        self._errorConexion.setWindowTitle("Error")
        try:
            #print(str(e.faultMessage[1].message))
            self._errorConexion.lineEdit.setPlainText(str(e.faultMessage[1].message))
        except:
            self._errorConexion.lineEdit.setPlainText("Hubo un problema al ejecutar la acción. ")
        self._errorConexion.exec_()

    #Salir
    def exit(self):
        self.close()


def getEsxiInfo():
    content = service_instance.RetrieveContent()
    for datacenter in content.rootFolder.childEntity:
        if hasattr(datacenter.hostFolder, 'childEntity'):
            computeResourceList = datacenter.hostFolder.childEntity
            for computeResource in computeResourceList:
                for host in computeResource.host:
                    try:
                        return (host.summary)
                    except Exception as error:
                        #print("Unable to access information for host: ", host.name)
                        #print(error)
                        pass


#Obtener nombres de cada datastore del conjunto total
def getDatastoresName():
    ds_names = []
    global datastores
    for ds in datastores:
        ds_names.append(ds.summary.name)
    #print (ds_names)
    return ds_names

#Convertidor de tamaño
def sizeof_fmt(num):
    for item in ['bytes', 'KB', 'MB', 'GB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, item)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')

#Cargar información de datastore
def print_datastore_info(cont,ventana,ds_obj,):
    table = ventana.datastoresTable
    summary = ds_obj.summary
    ds_capacity = summary.capacity
    ds_freespace = summary.freeSpace
    ds_uncommitted = summary.uncommitted if summary.uncommitted else 0
    ds_provisioned = ds_capacity - ds_freespace + ds_uncommitted
    ds_overp = ds_provisioned - ds_capacity
    ds_overp_pct = (ds_overp * 100) / ds_capacity \
        if ds_capacity else 0

    table.setItem(cont, 0, QTableWidgetItem(summary.name))
    table.setItem(cont, 1, QTableWidgetItem(summary.url))
    table.setItem(cont, 2, QTableWidgetItem(summary.type))
    table.setItem(cont, 3, QTableWidgetItem(sizeof_fmt(ds_capacity)))
    table.setItem(cont, 4, QTableWidgetItem(sizeof_fmt(ds_freespace)))
    table.setItem(cont, 5, QTableWidgetItem(sizeof_fmt(ds_uncommitted)))
    table.setItem(cont, 6, QTableWidgetItem(sizeof_fmt(ds_provisioned)))
    if ds_overp > 0:
        table.setItem(cont, 7, QTableWidgetItem(format(sizeof_fmt(ds_overp),ds_overp_pct)))
    else:
        table.setItem(cont, 7, QTableWidgetItem("0"))
    table.setItem(cont, 8, QTableWidgetItem(format(len(ds_obj.host))))
    table.setItem(cont, 9, QTableWidgetItem(format(len(ds_obj.vm))))

#Obtener objetos
def get_obj(content, vim_type, name=None):
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vim_type, True)
    if name:
        for c in container.view:
            if c.name == name:
                obj = c
                return [obj]
    else:
        return container.view

#Mostrar información de las máquinas virtuales
def print_vm_info(cont,virtual_machine, ventana):
    summary = virtual_machine.summary
    table = ventana.mvTable
    global vms
    vms.append(summary)
    #print(summary)
    table.setItem(cont, 0, QTableWidgetItem(summary.config.name))
    table.setItem(cont, 1, QTableWidgetItem(summary.config.instanceUuid))
    table.setItem(cont, 2, QTableWidgetItem(summary.config.guestFullName))
    if (summary.runtime.powerState=="poweredOn"):
        table.setItem(cont, 3, QTableWidgetItem("Encendida"))
    else:
        table.setItem(cont, 3, QTableWidgetItem("Apagada"))
    table.setItem(cont, 4, QTableWidgetItem(str(summary.config.numCpu)))
    table.setItem(cont, 5, QTableWidgetItem(str(summary.config.memorySizeMB)))
    if summary.guest is not None:
        ip_address = summary.guest.ipAddress
        tools_version = summary.guest.toolsStatus
        if (tools_version!="toolsNotInstalled"):
            toolsv="VMware-tools: "+ tools_version
            table.setItem(cont, 6, QTableWidgetItem(toolsv))
        else:
            table.setItem(cont, 6, QTableWidgetItem("VMware-tools: NO"))
        if ip_address:
            table.setItem(cont, 7, QTableWidgetItem(ip_address))
        else:
            table.setItem(cont, 7, QTableWidgetItem("Desconocida"))


#Saltar Warning con SSL
def avoid_ssl():
    # Saltar cerfificado SSL
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        # Legacy Python that doesn't verify HTTPS certificates by default
        pass
    else:
        # Handle target environment that doesn't support HTTPS verification
        ssl._create_default_https_context = _create_unverified_https_context


def main():
    avoid_ssl()
    # Instancia para iniciar una aplicación
    app = QApplication(sys.argv)

    # Crear un objeto de la clase
    _ventana = HypervisorMainWindow()

    # Mostra la ventana
    _ventana.show()
    # Ejecutar la aplicación
    app.exec_()


# Start program
if __name__ == "__main__":
    main()
