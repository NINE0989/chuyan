# -*- coding: utf-8 -*-
import pyaudio
import numpy as np

class AudioRecorder:
    """
    一个使用 PyAudio 监听系统回环音频的类。
    """
    def __init__(self, rate=44100, chunk_size=4096):
        self.rate = rate
        self.chunk_size = chunk_size
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.device_index = None

    def find_loopback_device(self):
        """
        通过遍历所有输入设备并检查名称，查找可用的回环设备。
        在 Windows 上，这通常是 'Stereo Mix' 或 '立体声混音'。
        """
        print("正在查找可用的回环音频设备 (如 'Stereo Mix')...")
        
        loopback_device_index = None
        
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            dev_name = dev_info['name'].lower()
            
            # 检查设备是否为输入设备，并且名称是否包含回环关键字
            if dev_info['maxInputChannels'] > 0 and ('stereo mix' in dev_name or '立体声混音' in dev_name):
                print(f"找到回环设备: {dev_info['name']}")
                loopback_device_index = i
                break
        
        if loopback_device_index is None:
            print("\n错误：未找到 'Stereo Mix' 或 '立体声混音' 设备！")
            print("请按以下步骤操作：")
            print("1. 右键点击任务栏的声音图标 -> 选择 '声音'。")
            print("2. 切换到 '录制' 选项卡。")
            print("3. 在空白处右键 -> 勾选 '显示禁用的设备'。")
            print("4. 找到 'Stereo Mix' 或 '立体声混音' -> 右键点击 -> 选择 '启用'。")
            return False
            
        dev_info = self.p.get_device_info_by_index(loopback_device_index)
        self.device_index = loopback_device_index
        # 使用设备支持的默认采样率
        self.rate = int(dev_info['defaultSampleRate'])
        # 使用设备支持的通道数
        self.channels = dev_info['maxInputChannels']
        
        print(f"已选择设备: '{dev_info['name']}' (采样率: {self.rate} Hz, 通道: {self.channels})")
        return True

    def start(self):
        """
        打开音频流以开始录制。
        """
        if self.find_loopback_device() is False:
            return False
            
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size
        )
        print("音频流已开启，正在监听...")
        return True

    def read(self):
        """
        从音频流中读取一个数据块。
        """
        if not self.stream:
            return None
        
        try:
            data = self.stream.read(self.chunk_size)
            if data is None:
                print("读取到空数据块")
                return None
            # 将字节数据转换为numpy数组
            np_data = np.frombuffer(data, dtype=np.int16)
            return np_data
        except IOError as e:
            print(f"读取音频流时出错: {e}")
            return None

    def stop(self):
        """
        停止并关闭音频流。
        """
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        print("音频流已关闭。")

if __name__ == '__main__':
    # 用于测试 AudioRecorder 类的独立运行
    recorder = AudioRecorder()
    if recorder.start():
        try:
            print("开始测试读取5秒...")
            for _ in range(int(5 * recorder.rate / recorder.chunk_size)):
                data = recorder.read()
                if data is not None:
                    print(f"成功读取数据块，大小: {data.shape}, 最大值: {np.max(data)}")
            print("测试完成。")
        finally:
            recorder.stop()
