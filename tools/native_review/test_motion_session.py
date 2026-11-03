"""Guard the scope and restoration of the reversible hardware IMU lease."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

path=Path(__file__).parent/'launchers/totk-motion-session.py'
spec=importlib.util.spec_from_file_location('motion_session',path)
lease=importlib.util.module_from_spec(spec);spec.loader.exec_module(lease)

class MotionSessionTests(unittest.TestCase):
    def test_only_imu_register_is_written(self):
        def ioctl(fd,op,data):
            self.assertEqual(fd,8);self.assertEqual(op,lease.HIDIOCSFEATURE)
            self.assertEqual(bytes(data[:6]),bytes([0,0x87,3,0x30,0x18,0]))
            self.assertEqual(set(data[6:]),{0})
        with mock.patch.object(lease.fcntl,'ioctl',side_effect=ioctl):lease.setting(8,0x18)
    def test_unrelated_feature_reply_is_rejected(self):
        with mock.patch.object(lease.fcntl,'ioctl'),mock.patch.object(lease.time,'sleep'):
            with self.assertRaises(OSError):lease.setting(8)
    def test_interleaved_reply_retries_only_read_queries(self):
        reads=[]
        def ioctl(fd,op,data):
            if op == lease.HIDIOCSFEATURE:
                self.assertEqual(bytes(data[:6]),bytes([0,0x89,3,0x30,0,0]))
            else:
                reads.append(1)
                if len(reads)==2:data[:6]=bytes([0,0x89,3,0x30,0x18,0])
        with mock.patch.object(lease.fcntl,'ioctl',side_effect=ioctl),mock.patch.object(lease.time,'sleep'):
            self.assertEqual(lease.setting(8),0x18)
        self.assertEqual(len(reads),2)
    def run_session(self,changed=False):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            state={'value':0};writes=[]
            def setting(fd,value=None):
                if value is not None:state['value']=value;writes.append(value)
                return state['value']
            child=mock.Mock();child.returncode=0
            def poll():
                if changed:state['value']=4
                return 0
            child.poll.side_effect=poll
            target=Path.home()/'native-recomp/ultratears/releases/v143-20261031-first/run.sh'
            with mock.patch.object(lease.sys,'argv',['helper',str(target)]),mock.patch.object(lease.Path,'resolve',return_value=target),mock.patch.dict(lease.os.environ,{'XDG_DATA_HOME':tmp,'TOTK_GYRO':'1','TOTK_STEAMDECK_GYRO':'1'}),mock.patch.object(lease,'open_imu',return_value=8),mock.patch.object(lease,'setting',side_effect=setting),mock.patch.object(lease.subprocess,'Popen',return_value=child),mock.patch.object(lease.signal,'signal'),mock.patch.object(lease.os,'close'):
                self.assertEqual(lease.main(),0)
            return writes,state['value']
    def test_clean_exit_restores_original_sensor_mode(self):
        self.assertEqual(self.run_session(),([0x18,0],0))
    def test_exit_preserves_a_later_owner_mode(self):
        self.assertEqual(self.run_session(changed=True),([0x18],4))

if __name__=='__main__':unittest.main()
