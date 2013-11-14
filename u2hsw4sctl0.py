#!/usr/bin/env python
# 
# Copyright (C) 2012 NONAKA Kimihiro <nonakap@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

#
# ELECOM U2H-SW4S USB port power control tool
#
# require: pyusb, libusb
# tested on python-2.6.6, pyusb-0.4.3, libusb-win32-bin-1.2.6.0
#

#
# Device Descriptor:
# bcdUSB:             0x0200
# bDeviceClass:         0x00
# bDeviceSubClass:      0x00
# bDeviceProtocol:      0x00
# bMaxPacketSize0:      0x40 (64)
# idVendor:           0x2101
# idProduct:          0x8501
# bcdDevice:          0x0605
# iManufacturer:        0x01
# iProduct:             0x02
# iSerialNumber:        0x00
# bNumConfigurations:   0x01
#
# ConnectionStatus: DeviceConnected
# Current Config Value: 0x01
# Device Bus Speed:     Full
# Device Address:       0x02
# Open Pipes:              1
#
# Endpoint Descriptor:
# bEndpointAddress:     0x82
# Transfer Type:   Interrupt
# wMaxPacketSize:     0x0008 (8)
# bInterval:            0x08
#

import usb
import struct

VENDOR=0x2101
PRODUCT=0x8501

ENDPOINT=0x82

PORT_MIN=1
PORT_MAX=4

PORT_FULLLIST = range(PORT_MIN, PORT_MAX + 1)

class U2HSW4SPortPower:

    def __init__(self, idVendor = VENDOR, idProduct = PRODUCT):
        busses = usb.busses()
        for bus in busses:
            devices = bus.devices
            for device in devices:
                if (device.idVendor, device.idProduct) == (idVendor, idProduct):
                    self.device = device
                    self.configuration = self.device.configurations[0]
                    self.interface = self.configuration.interfaces[0][0]
                    self.endpoints = []
                    self.pipes = []
                    for ep in self.interface.endpoints:
                        self.endpoints.append(ep)
                        self.pipes.append(ep.address)
                    return
        raise RuntimeError, 'Device not found'

    def __del__(self):
        if hasattr(self, 'handle'):
            try:
                self.close()
            except RuntimeError:
                pass

    def open(self):
        if hasattr(self, 'handle'):
            raise RuntimeError, 'Device already opened'
        self.handle = self.device.open()
        self.handle.setConfiguration(self.configuration)
        self.handle.claimInterface(self.interface)
        self.handle.setAltInterface(self.interface)

    def close(self):
        if hasattr(self, 'handle'):
            self.handle.releaseInterface()
            del self.handle
        else:
            raise RuntimeError, 'Device not opened'

    #
    # Send control message
    #
    def _send(self, msg):
        return self.handle.controlMsg(requestType = usb.ENDPOINT_OUT | usb.TYPE_CLASS | usb.RECIP_INTERFACE, request = 9, value = 0x203, buffer = msg, timeout = 100)

    #
    # Convert port# to address#
    #
    def _port_to_addr(self, port):
        addrs = ( 5, 2, 3, 4 )
        if port < 1:
            return -1
        port = port - 1
        if port >= len(addrs):
            return -1
        return addrs[port]

    #
    # Get port status
    #
    def getStatus(self):
        msg = '\x03\x5d\x02\x00\x00\x00\x00\x00'
        assert len(msg) == 8
        ret = self._send(msg)
        assert ret == 8

        data = self.handle.interruptRead(ENDPOINT, 8, 100)
        assert len(data) == 8
        assert data[0] == 0x03
        assert data[1] == 0x5d
        assert data[3] == 0x00
        assert data[4] == 0x75
        assert data[5] == 0x00
        assert data[6] == 0x00
        assert data[7] == 0x00

        status = {}
        for port in PORT_FULLLIST:
            addr = self._port_to_addr(port)
            assert addr >= 0
            status[port] = (data[2] >> addr) & 1
        return status

    #
    # Set port power
    #
    def setPower(self, port, onoff):
        addr = self._port_to_addr(port)
        assert addr >= 0
        msg = struct.pack('BBBBBBBB', 0x03, 0x5d, 0x00, addr, onoff, 0x00, 0x00, 0x00)
        assert len(msg) == 8
        ret = self._send(msg)
        assert ret == 8

if __name__ == '__main__':
    import sys
    argc = len(sys.argv)
    argv = sys.argv

    def usage():
        print 'Usage: %s [<port> [onoff]]' % argv[0]
        print 'port : 1-4'
        print 'onoff: on, off'
        quit()

    if argc < 1 or argc >= 4:
        usage()

    inst = U2HSW4SPortPower()
    inst.open()

    def getStatus(port, status):
        pstatus = ( 'Off', 'On' )
        return pstatus[status[port]]

    if argc == 1:
        status = inst.getStatus()
        for port in PORT_FULLLIST:
            print "Port%d: %s" % (port, getStatus(port, status))
        status = inst.getStatus()   # dummy read
        quit()

    port = int(argv[1])
    if port < PORT_MIN or port > PORT_MAX:
        usage()

    if argc == 2:
        status = inst.getStatus()
        print getStatus(port, status)
        status = inst.getStatus()   # dummy read
        quit()

    if argv[2].upper() == "ON":
        onoff = 1
    elif argv[2].upper() == "OFF":
        onoff = 0
    else:
        usage()

    oldstatus = inst.getStatus()
    inst.setPower(port, onoff)
    newstatus = inst.getStatus()
    print "Port%d: %s -> %s" % (port, getStatus(port, oldstatus), getStatus(port, newstatus))
