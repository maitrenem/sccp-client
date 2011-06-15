""" 
Sample PyQt GUI using a Twisted-based socket client. Demonstrates how to make
PyQt work in unison with Twisted.

Eli Bendersky (eliben@gmail.com)
This code is in the public domain
"""
import os, sys, time
import Queue
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from struct import pack

from sccp.sccpmessage import SCCPMessage
from sccp.sccpmessagetype import SCCPMessageType
import struct
from sccp.sccpregister import SCCPRegister
from network.sccpclientfactory import SCCPClientFactory
from sccp.sccpcapabilities import SCCPCapabilitiesRes

SERVER_HOST = '192.168.30.83'
SERVER_PORT = 2000
DEVICE_NAME= 'SEP00164697AAAA'


class CircleWidget(QWidget):
    def __init__(self, parent=None):
        super(CircleWidget, self).__init__(parent)
        self.nframe = 0
        self.setBackgroundRole(QPalette.Base)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.connected = False

    def minimumSizeHint(self):
        return QSize(50, 50)

    def sizeHint(self):
        return QSize(50, 50)

    def next(self):
        self.nframe += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)

        for diameter in range(0, 32, 9):
            delta = abs((self.nframe % 64) - diameter / 2)
            alpha = 255 - (delta * delta) / 4 - diameter
            if alpha > 0:
                if (self.connected):
                    painter.setPen(QPen(QColor(0, 192, 0, alpha), 3))
                else:    
                    painter.setPen(QPen(QColor(255, 0, 0, alpha), 3))
                painter.drawEllipse(QRectF(
                    -diameter / 2.0,
                    -diameter / 2.0, 
                    diameter, 
                    diameter))


class LogWidget(QTextBrowser):
    def __init__(self, parent=None):
        super(LogWidget, self).__init__(parent)
        palette = QPalette()
        palette.setColor(QPalette.Base, QColor("#ddddfd"))
        self.setPalette(palette)


class SCCPClientWindow(QMainWindow):
    def __init__(self, reactor, parent=None):
        super(SCCPClientWindow, self).__init__(parent)
        self.reactor = reactor
        
        self.create_main_frame()
        self.create_client()
        self.create_timer()

    def create_main_frame(self):
        self.circle_widget = CircleWidget()
        self.doit_button = QPushButton('Connect !')
        self.doit_button.clicked.connect(self.on_doit)
        self.log_widget = LogWidget()
        hostLabel = QLabel("Host : ")
        self.hostEdit = QLineEdit()
        self.hostEdit.setText(SERVER_HOST)
        deviceNameLabel = QLabel("Phone Set : ")
        self.deviceNameEdit = QLineEdit()
        self.deviceNameEdit.setText(DEVICE_NAME)
        
        hbox = QVBoxLayout()
        hbox.addWidget(self.circle_widget)
        
        hostBox = QHBoxLayout()
        hostBox.addWidget(hostLabel)
        hostBox.addWidget(self.hostEdit)
        hbox.addLayout(hostBox)
        deviceBox = QHBoxLayout()
        deviceBox.addWidget(deviceNameLabel)
        deviceBox.addWidget(self.deviceNameEdit)
        hbox.addLayout(deviceBox)

        hbox.addWidget(self.doit_button)
        hbox.addWidget(self.log_widget)

                
        main_frame = QWidget()
        main_frame.setLayout(hbox)
        main_frame.setMinimumWidth(400)
        
        self.setCentralWidget(main_frame)
        
    def create_timer(self):
        self.circle_timer = QTimer(self)
        self.circle_timer.timeout.connect(self.circle_widget.next)
        self.circle_timer.start(25)
    
    def create_keepalive_timer(self):
        self.circle_timer = QTimer(self)
        self.circle_timer.timeout.connect(self.circle_widget.next)
        self.circle_timer.start(25)
        
    def create_client(self):
        self.client = SCCPClientFactory(
                        self.on_client_connect_success,
                        self.on_client_connect_fail,
                        self.on_client_receive)
        self.client.handleUnknownMessage(self.onUnknownMessage)
        self.client.addHandler(SCCPMessageType.RegisterAckMessage,self.onRegisteredAck)
        self.client.addHandler(SCCPMessageType.CapabilitiesReqMessage,self.onCapabilitiesReq)
        self.client.addHandler(SCCPMessageType.KeepAliveAckMessage,self.onKeepAliveAck)
        
    
    def on_doit(self):
       
        serverHost = str(self.hostEdit.text())
        self.log("trying to connect to : "+serverHost+ " on " +`SERVER_PORT`)
        self.connection = self.reactor.connectTCP(serverHost, SERVER_PORT, self.client)

    def on_client_connect_success(self):
        deviceName = str(self.deviceNameEdit.text())
        self.log('Connected to server. Sending register with phone set : ' + deviceName)
        registerMessage = SCCPRegister(deviceName, "192.168.30.84")
        self.client.send_msg(registerMessage.pack())
    
    def onRegisteredAck(self,registerAck):
        self.log("sccp phone registered")
        self.log("          keepAliveInterval : " + `registerAck.keepAliveInterval`)
        self.log("               dateTemplate : " + `registerAck.dateTemplate`)
        self.log(" secondaryKeepAliveInterval : " + `registerAck.secondaryKeepAliveInterval`)
#        self.sendKeepAlive()
        self.keepalive_timer = QTimer(self)
        self.keepalive_timer.timeout.connect(self.sendKeepAlive)
        self.keepalive_timer.start(registerAck.keepAliveInterval*1000)
        self.circle_widget.connected = True
    
    def onCapabilitiesReq(self,message):
        self.log("on capabilities request")
        capabilities = SCCPCapabilitiesRes()
        self.client.send_msg(capabilities.pack())
        message = SCCPMessage(SCCPMessageType.TimeDateReqMessage)
        self.client.send_msg(message.pack())
        
    def onKeepAliveAck(self,message):
        self.log("Keepalive ack")
  
    def sendKeepAlive(self):
        self.log("sending keepalive")
        message = SCCPMessage(SCCPMessageType.KeepAliveMessage)
        strMessage = message.pack();
        self.client.send_msg(strMessage)
        
    def on_client_connect_fail(self, reason):
        # reason is a twisted.python.failure.Failure  object
        self.log('Connection failed: %s' % reason.getErrorMessage())
        
    def on_client_receive(self, msg):
        self.log('server reply: %d' % len(msg))
        messageType = struct.unpack("L",msg[4:8])[0]
        self.log( "message type " + str(messageType))

        #self.connection.disconnect()
        
    def onUnknownMessage(self,message):
        self.log('receive unkown message ' + message.toStr())
        
    def log(self, msg):
        timestamp = '[%010.3f]' % time.clock()
        self.log_widget.append(timestamp + ' ' + str(msg))

    def closeEvent(self, e):
        self.log("close event")
        self.reactor.stop()


#-------------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    
    from twisted.internet import reactor
    mainwindow = SCCPClientWindow(reactor)
    mainwindow.show()
    
    reactor.run()