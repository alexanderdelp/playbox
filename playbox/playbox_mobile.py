import sys
import nfc
import nfc.tag
import time
from binascii import hexlify
from threading import Lock
from nfc.clf import RemoteTarget
from mpd import MPDClient
from mpd import ConnectionError


class MPDClientWrapper(MPDClient):
   def __init__(self, host="localhost", port=6600):
      print("|| enter: MPDClientWrapper.__init__()")
      super(MPDClientWrapper, self).__init__()
      self._host = host
      self._port = port
      self._lock = Lock()
      print("|| exit: MPDClientWrapper.__init__()")

   def acquire(self):
      print("|| enter: MPDClientWrapper.acquire()")
      self._lock.acquire()
      print("|| exit: MPDClientWrapper.acquire()")

   def release(self):
      print("|| enter: MPDClientWrapper.release()")
      self._lock.release()
      print("|| exit: MPDClientWrapper.release()")

   def __enter__(self):
      print("|| enter: MPDClientWrapper.__enter__()")
      self.acquire()
      try:
         self.ping()
      except(ConnectionError, OSError):
         print("|| except: ConnectionError")
         self.do_connect()
      print("|| exit: MPDClientWrapper.__enter__()")

   def __exit__(self, type, value, traceback):
      print("|| enter: MPDClientWrapper.__exit__()")
      self.release()
      print("|| exit: MPDClientWrapper.__exit__()")

   def do_connect(self):
      print("|| enter: MPDClientWrapper.do_connect()")
      try:
         try:
            self.disconnect()
         # if it's a TCP connection, we'll get a socket error
         # if we try to disconnect when the connection is lost
         except ConnectionError:
            print("|| except: ConnectionError")
            pass
         # if it's a socket connection, we'll get a BrokenPipeError
         # if we try to disconnect when the connection is lost
         # but we have to retry the disconnect, because we'll get
         # an "Already connected" error if we don't.
         # the second one should succeed.
         except BrokenPipeError:
            print("|| except: BrokenPipeError")
            try:
               self.disconnect()
            except:
               print("|| except")
         self.connect(self._host, self._port)
      except socket.error:
         print("|| except: socket.error")
      print("|| exit: MPDClientWrapper.do_connect()")


class Player(object):
   def __init__(self):
      print("|| enter: Player.__init__()")
      self.mpdClient = MPDClientWrapper(host="localhost", port=6600)
      self.initMPDClient()
      print("|| exit: Player.__init__()")

   def initMPDClient(self):
      print("|| enter: Player.initMPDClient()")
      with self.mpdClient:
         self.mpdClient.update()
         self.mpdClient.clear()
      print("|| exit: Player.initMPDClient()")

   def rewind(self, seconds):
      print("|| enter: Player.rewind()")
      with self.mpdClient:
         mpdClientStatus = self.mpdClient.status()
         currentTrackPosition = float(mpdClientStatus['elapsed'])
         newTrackPosition = max(currentTrackPosition - seconds, 0)
         self.mpdClient.seek(0, newTrackPosition)
      print("|| enter: Player.rewind()")

   def pauseCurrentTrack(self):
      print("|| enter: Player.pauseCurrentTrack()")
      with self.mpdClient:
         self.mpdClient.pause()
      print("|| enter: Player.pauseCurrentTrack()")

   def resumePausedTrack(self):
      print("|| enter: Player.resumePausedTrack()")
      self.rewind(2)
      with self.mpdClient:
         self.mpdClient.play()
      print("|| enter: Player.resumePausedTrack()")

   def playNewTrack(self, trackName):
      print("|| enter: Player.playNewTrack()")
      with self.mpdClient:
         self.mpdClient.stop()
         self.mpdClient.clear()
         self.mpdClient.add(trackName)
         self.mpdClient.play()
      print("|| enter: Player.playNewTrack()")

   def closeMPDClient(self):
      print("|| enter: Player.closeMPDClient()")
      with self.mpdClient:
         self.mpdClient.stop()
         self.mpdClient.close()
         self.mpdClient.disconnect()
      print("|| enter: Player.closeMPDClient()")


class TagDatabase(object):
   def __init__(self):
      pass

   def getTrackFromId(self, id):
      if id == "0469416A643480":
         return {'title': 'Conni hat Geburtstag', 'file': 'Geburtstag.mp3'}
      elif id == "0422D9F2794D81":
         return {'title': 'Conni bekommt eine Katze', 'file': 'conni_kater_mau.mp3'}
      elif id == "67A6094E":
         sys.exit()
      else:
         return None


def connected(tag):
   global player
   global tagDatabase

   global idOfLastCard
   print("tag connected...")
   idOfNewCard = hexlify(tag.identifier).decode().upper()
   print("... id: " + idOfNewCard)

   if idOfNewCard == idOfLastCard:
      print("... resuming last audio book")
      player.resumePausedTrack()
   else:
      print("... starting new audio book")
      trackToPlay = tagDatabase.getTrackFromId(idOfNewCard)
      if trackToPlay != None:
         print("... audio book: " + trackToPlay['title'])
         player.playNewTrack(trackToPlay['file'])
      idOfLastCard = idOfNewCard 
   return True

def released(tag):
   global player
   print("tag released...")
   print("... pausing play")
   player.pauseCurrentTrack()
   return True


def connect(onconnected, onreleased):
   global clf
   requiredRemoteTargetType = RemoteTarget('106A')

   print("sensing for target...")
   clf.device.chipset.ccid_xfr_block(bytearray.fromhex("FF00400C0400000000"))#turn_on_led_and_buzzer()
   while True:
      sensedTarget = clf.sense(requiredRemoteTargetType, iterations=5, interval=0.5)
      if sensedTarget != None:
         print("... target '%s' found" % sensedTarget)
         currentTag = nfc.tag.activate(clf, sensedTarget)
         if currentTag != None:
            print("... tag '%s'" % currentTag)
            clf.device.turn_off_led_and_buzzer()
            onconnected(currentTag)
            print("... sleeping for grace period")
            time.sleep(3.0)
            print("... entering presence loop")
            while True:
               newTarget = clf.sense(requiredRemoteTargetType, iterations=1)
               if newTarget is None:
                  clf.device.chipset.ccid_xfr_block(bytearray.fromhex("FF00400C0400000000"))#turn_on_led_and_buzzer()
                  onreleased(currentTag)
                  break
               newTag = nfc.tag.activate(clf, newTarget)
               if newTag is None:
                  clf.device.chipset.ccid_xfr_block(bytearray.fromhex("FF00400C0400000000"))#turn_on_led_and_buzzer()
                  onreleased(currentTag)
                  break
               if currentTag.identifier != newTag.identifier:
                  clf.device.chipset.ccid_xfr_block(bytearray.fromhex("FF00400C0400000000"))#turn_on_led_and_buzzer()
                  onreleased(currentTag)
                  break
               time.sleep(0.1)
#if options['beep-on-connect']:
#   self.device.turn_on_led_and_buzzer()
#self.device.turn_off_led_and_buzzer() = gruen = .ccid_xfr_block(bytearray.fromhex("FF00400E0400000000"))
#    def close(self):
#        self.ccid_xfr_block(bytearray.fromhex("FF00400C0400000000"))
#        self.transport.close()
#        self.transport = None
#
#    def set_buzzer_and_led_to_default(self):
#        """Turn off buzzer and set LED to default (green only). """
#        self.ccid_xfr_block(bytearray.fromhex("FF00400E0400000000"))
#    def set_buzzer_and_led_to_active(self, duration_in_ms=300):
#        """Turn on buzzer and set LED to red only. The timeout here must exceed
#         the total buzzer/flash duration defined in bytes 5-8. """
#        duration_in_tenths_of_second = int(min(duration_in_ms / 100, 255))
#        timeout_in_seconds = (duration_in_tenths_of_second + 1) / 10.0
#        data = "FF00400D04{:02X}000101".format(duration_in_tenths_of_second)
#        self.ccid_xfr_block(bytearray.fromhex(data),
#                            timeout=timeout_in_seconds)

player = Player()
tagDatabase = TagDatabase()
idOfLastCard = None
clf = nfc.ContactlessFrontend('usb')

def main():
   global clf
   global player
   try:
      print("looping")
      connect(connected, released)
   finally:
      clf.close()
      player.closeMPDClient()

if __name__ == "__main__":
   main()
