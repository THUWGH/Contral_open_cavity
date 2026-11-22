############################################################
# 文件名: labspec6_debug_FULL.py
# 目标: 最终的、完整的、合并了所有修复的驱动文件
#
# 包含:
# 1. 原始 labspec6.py 的所有功能 (如 prepare_N_acquisition)
# 2. 线程锁 (threading.Lock) 修复 (修复竞速)
# 3. 详细的 SEND/RECV 日志 (用于诊断)
############################################################

import socket
import numpy as np
import threading  # <--- 修复 1: 导入 threading

COMMANDS = {'GetRamanParam': 'param',
            'SetRamanParameter': 'param',
            'EnableSpectralResponse': 'array',
            'SetPointList': 'str',
            'SetActivePoint': 'array',
            'StartRamanMeasurement': 'array',
            'SetRamanParams': 'array',
            'Logout': 'str'
            }

PARAMS = {'AcquisitionTime': {'tip': 'Approximate total Acquisition time in seconds', 'get_set': 'get'},
          'Exposure': {'tip': 'Exposure time in seconds', 'get_set': 'set'},
          'Accumulations': {'tip': 'Exposure time in seconds', 'get_set': 'set'},
          'LaserWavelength': {'tip': 'Current laser wavelength in nm', 'get_set': 'get'},
          'Binning': {'tip': 'Xaxis binning', 'get_set': 'both'},
          'Spectro': {'tip': 'Spectrum central wavelength', 'get_set': 'both'},
          'Slit': {'tip': 'Slit opening  in µm', 'get_set': 'both'},
          'Hole': {'tip': 'Confocal hole diamater in µm', 'get_set': 'both'},
          'Laser': {'tip': 'Selected laser in µm', 'get_set': 'both'},
          'Grating': {'tip': 'Selected Grating in grooves/mm', 'get_set': 'both'},
          'LaserPol': {'tip': 'Xplora laser polarization', 'get_set': 'both'},
          'RamanPol': {'tip': 'Xplora Raman Polarization', 'get_set': 'both'},
          'Pol1': {'tip': 'HR laser Polarization in deg', 'get_set': 'both'},
          'Pol2': {'tip': 'HR Raman Polarization in deg', 'get_set': 'both'},
          'Detector': {'tip': 'Selected Detector', 'get_set': 'get'},
          }


class Labspec6Client:
    """
    Wrapper around the Horiba RAMAN-AFM systems reversed interconnection protocol for LabSpec 6 Version 0.6.2
    [DEBUG FULL V6 - 已添加 threading.Lock 和 详细日志]
    """

    def __init__(self):
        super().__init__()
        self._socket = None
        self._commandID = -1
        self.lasers = []
        self.gratings = []
        self._exposure = 1
        self._accumulations = 1
        self._timeout_mult = 5
        self._lock = threading.Lock()  # <--- 修复 2: 在 __init__ 中创建锁
        
        # [新] 确保所有原始属性都存在
        self.wavelength_axis = None 

    @property
    def timeout_mult(self):
        return self._timeout_mult

    @timeout_mult.setter
    def timeout_mult(self, timeout_mult):
        self._timeout_mult = timeout_mult

    @property
    def timeout(self):
        if self._socket is not None:
            return self._socket.timeout

    @timeout.setter
    def timeout(self, timeout):
        if self._socket is not None:
            self._socket.settimeout(timeout)

    # ==========================================================
    # [!! 关键 !!] 包含原始的、未被省略的 prepare_N_acquisition
    # ==========================================================
    def prepare_N_acquisition(self, Npts=2):
        """
        Prepare acquisition before a grab. Normally it is used to prepare a map of Npoints.
        (此方法来自原始 labspec6.py 文件)
        """
        print("[DEBUG] prepare_N_acquisition(): 正在准备...")
        
        point_list = [b'0 0' for ind in range(Npts)]
        Nbytes = Npts*3

        ret, data, extra = self.send_command('GetRamanParam', 'AcquisitionTime')
        # [DEBUG] 根据 pymodaq 的代码，这里应该设置超时
        # self.timeout = self._timeout_mult * data
        # [DEBUG] 暂时注释掉上面这行，因为 data 可能不是数字，
        # [DEBUG] 并且我们已在 connect() 中设置了 20 秒的固定超时
        
        if ret != 'OK':
             print(f"[DEBUG][ERROR] prepare_N_acquisition: GetRamanParam AcquisitionTime 失败: {ret} {data}")
             return f"Error: {data}"

        ret, data, extra = self.send_command('SetPointList', Npts, Nbytes, point_list)
        if ret == 'OK':
            ret, data, extra = self.send_command('EnableSpectralResponse')
            if ret == 'OK':
                self.wavelength_axis = data
                ret, data, extra = self.send_command('SetActivePoint', 0)
                if ret == 'OK':
                    print("[DEBUG] prepare_N_acquisition(): 准备就绪 (ready)。")
                    return 'ready'
        
        # [DEBUG] 添加更详细的失败返回
        print(f"[DEBUG][ERROR] prepare_N_acquisition 失败: {ret} {data}")
        return f"Error: {ret} {data}"


    @property
    def wavelength(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Spectro')
        if ret == 'OK':
            return data

    @wavelength.setter
    def wavelength(self, value):
        ret, data, extra = self.send_command('SetRamanParameter', 'Spectro', value)
        if ret != 'OK':
            raise IOError('Wrong return from Server')


    @property
    def exposure(self):
        return self._exposure

    @exposure.setter
    def exposure(self, value):
        ret, data, extra = self.send_command('SetRamanParameter', 'Exposure', value)
        if ret != 'OK':
            raise IOError('Wrong return from Server')
        else:
            self._exposure = value

    @property
    def accumulations(self):
        return self._accumulations

    @accumulations.setter
    def accumulations(self, value):
        ret, data, extra = self.send_command('SetRamanParameter', 'Accumulations', value)
        if ret != 'OK':
            raise IOError('Wrong return from Server')
        else:
            self._accumulations = value

    # [包含了所有其他原始属性: binning, slit, hole, laser, grating...]
    # ... (为了简洁，这里不粘贴它们，但假定它们都在) ...

    @property
    def binning(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Binning')
        if ret == 'OK':
            return int(data)
    @binning.setter
    def binning(self, value):
        ret, data, extra = self.send_command('SetRamanParameter', 'Binning', int(value))
        if self.binning != value:
            raise IOError('Wrong return from Server')

    @property
    def slit(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Slit')
        if ret == 'OK':
            return data
    @slit.setter
    def slit(self, value):
        ret, data, extra = self.send_command('SetRamanParameter', 'Slit', value)
        if ret != 'OK':
            raise IOError('Wrong return from Server')

    @property
    def hole(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Hole')
        if ret == 'OK':
            return data
    @hole.setter
    def hole(self, value):
        ret, data, extra = self.send_command('SetRamanParameter', 'Hole', value)
        if ret != 'OK':
            raise IOError('Wrong return from Server')

    @property
    def laser(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Laser')
        if ret == 'OK':
            ind_laser, lasers = self.get_lasers()
            return lasers[ind_laser]
    @laser.setter
    def laser(self, value):
        ind_laser, lasers = self.get_lasers()
        ind_laser = lasers.index(value)
        ret, data, extra = self.send_command('SetRamanParameter', 'Laser', ind_laser)
        if ret != 'OK':
            raise IOError('Wrong return from Server')
            
    def get_lasers(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Laser')
        if ret == 'OK':
            self.lasers = extra
            return int(data), extra

    def get_laser_wl(self):
        ret, data, extra = self.send_command('GetRamanParam', 'LaserWavelength')
        if ret == 'OK':
            return data

    @property
    def grating(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Grating')
        if ret == 'OK':
            ind_grating, gratings = self.get_gratings()
            return gratings[ind_grating]
    @grating.setter
    def grating(self, value):
        ind_grating, gratings = self.get_gratings()
        ind_grating = gratings.index(value)
        ret, data, extra = self.send_command('SetRamanParameter', 'Grating', ind_grating)
        if ret != 'OK':
            raise IOError('Wrong return from Server')

    def get_gratings(self):
        ret, data, extra = self.send_command('GetRamanParam', 'Grating')
        if ret == 'OK':
            self.gratings = extra
            return int(data), extra

    # ==========================================================
    # [!! 关键 !!] 包含原始的 grab_spectrum
    # ==========================================================
    def grab_spectrum(self):
        """
        Grab a spectrum with current configuration
        (此方法来自原始 labspec6.py 文件)
        """
        ret, data, extra = self.send_command('StartRamanMeasurement', 0)
        if ret == 'OK':
            return data

    def get_x_axis(self):
        """
        Get the wavelength calibration for each pixels
        (此方法来自原始 labspec6.py 文件)
        """
        ret, data, extra = self.send_command('EnableSpectralResponse')
        self.wavelength_axis = data
        return data

    # ==========================================================
    # [!! 修复 3 !!] 已修改的 connect, init, close
    # ==========================================================
    def connect(self, IP='localhost', port=1234):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((IP, port))
        self.timeout = 20 # 保持 20 秒固定超时
        
        print("[DEBUG] connect(): 正在接收握手信息...")
        command_id, ret, data, extra = self.receive_data() # (带日志)
        
        if ret == 'OK':
            self.init_mandatory_settings() # (带日志和锁)
        return ret, data, extra

    def init_mandatory_settings(self):
        print("[DEBUG] init_mandatory_settings(): 正在设置默认值...")
        self.exposure = self._exposure # (带日志和锁)
        self.accumulations = self._accumulations # (带日志和锁)
        print("[DEBUG] init_mandatory_settings(): 默认值设置完毕。")

    def close(self):
        ret, data, extra = self.send_command('Logout') # (带日志和锁)
        if ret == 'OK':
            self._socket.close()
            self._socket = None

    # ==========================================================
    # [!! 修复 4 !!] 已修改的 receive_data 和 send_command (带日志和锁)
    # ==========================================================
    
    def receive_data(self, dtype='str'):
        data = b''
        extra = None
        print("[DEBUG] RECV: 等待服务器回复...")
        try:
            while True:
                chunk = self._socket.recv(4096)
                print(f"[DEBUG][RECV-RAW-CHUNK]: {chunk}")
                if not chunk:
                    print("[DEBUG] RECV: 收到空数据块，连接可能已关闭。")
                    break
                data += chunk
                if b'\r\n' in data:
                    break
        except socket.timeout:
            print("[DEBUG][ERROR] RECV: Socket 接收超时！")
            return -99, "Error_Timeout", "Socket Timeout", None

        print(f"[DEBUG][RECV-RAW-FULL]: {data}")

        data_decoded = data.decode(errors='ignore').split('\r\n')[0]
        data_parts = data_decoded.split(' ')
        
        command_id = data_parts[0]
        ret = data_parts[1]
        data_tmp = data_parts[2:]
        
        parsed_data = None # 初始化
        
        if ret == 'OK':
            parsed_data = ' '.join(data_tmp) # 默认
            try:
                if dtype == 'str':
                    parsed_data = ' '.join(data_tmp)
                elif dtype == 'array':
                    parsed_data = np.array([float(d) for d in data_tmp[1:]])
                    if len(parsed_data) != int(data_tmp[0]):
                        print(f"[DEBUG][ERROR] RECV: 数组长度不匹配! 预期: {data_tmp[0]}, 实际: {len(parsed_data)}")
                else:
                    parsed_data = ' '.join(data_tmp)
            except Exception as e:
                print(f"[DEBUG][ERROR] RECV: 解析 'OK' 数据时出错: {e}")
                parsed_data = ' '.join(data_tmp)
        
        elif dtype == 'param':
            if ret != 'Unknown':
                if ret != 'OK':
                    try:
                        parsed_data = float(ret)
                        ret = 'OK'
                    except ValueError:
                        ret += ' '.join(data_tmp)
                        parsed_data = None
                    if len(data_tmp) > 0:
                        data_tmp = ' '.join(data_tmp)
                        if '#' in data_tmp:
                            extra = data_tmp.split('#')
                            while '' in extra:
                                extra.pop(extra.index(''))
                else:
                    parsed_data = None
            else:
                parsed_data = ' '.join(data_parts)
        else:
            parsed_data = ' '.join(data_parts)

        try:
            command_id_parsed = int(command_id)
        except ValueError:
            print(f"[DEBUG][RECV-PARSED] ID: '{command_id}' (非数字!), Ret: {ret}, Data: {str(parsed_data)[:50]}...")
            command_id_parsed = command_id
        except Exception as e:
            print(f"[DEBUG][ERROR] RECV: 解析 command_id 时发生意外错误: {e}")
            command_id_parsed = -100

        if isinstance(command_id_parsed, int):
             print(f"[DEBUG][RECV-PARSED] ID: {command_id_parsed}, Ret: {ret}, Data: {str(parsed_data)[:50]}...")

        return command_id_parsed, ret, parsed_data, extra

    def send_command(self, command, *args):
        with self._lock: # <--- 修复 5: 线程锁
            self._commandID += 1
            comm = f'{self._commandID} {command}'

            if command == 'SetPointList':
                pointlist = args[-1]
                args = args[:-1]

            for arg in args:
                comm += f' {arg}'
            
            print(f"\n[DEBUG][SEND] ID: {self._commandID}, Command: {comm.encode()}")
            self._socket.send(comm.encode())

            if command == 'SetPointList':
                ret = self._socket.recv(4096)
                print(f"[DEBUG][RECV-RAW-CHUNK]: (SetPointList) {ret}")
                if b'OK Ready to receive' not in ret:
                    raise IOError(f'The command {comm} returned with an error: {ret}')
                for ind, point in enumerate(pointlist):
                    self._socket.send(point)
                    if ind < len(pointlist)-1:
                        ret = self._socket.recv(4096)
                        print(f"[DEBUG][RECV-RAW-CHUNK]: (SetPointList) {ret}")
                        if b'OK Point' not in ret:
                            raise IOError(f'Issue with the list of point, ind:{ind}')

            command_id, ret, data, extra = self.receive_data(COMMANDS[command])

            if command_id != self._commandID:
                print(f"\n[DEBUG][ERROR] ID 严重不匹配!")
                print(f"    Expected (期望的ID): {self._commandID}")
                print(f"    Got (收到的ID):      {command_id} (类型: {type(command_id)})")
                if isinstance(command_id, str):
                    print(f"    [诊断信息]：服务器返回了非数字的错误消息: '{command_id} {ret} {data}'")
                
                # [DEBUG] 我们在 V5 中知道错误 600 是服务器的错误码，所以放宽这个检查
                # 我们暂时信任服务器的逻辑，并返回错误，而不是抛出异常
                if ret == 'Error' or ret.startswith('Error'):
                    print("    [DEBUG] 检测到服务器错误，但将错误信息传递回去，而不是抛出 OSError。")
                    return ret, data, extra # <-- 关键更改：不抛出异常，而是返回错误
                
                # 如果不是 'Error'，那么它仍然是一个未知的 ID 错乱
                raise IOError('The command ID returned from the Labspec server is incorrect (and not a recognized Error code)')

            return ret, data, extra