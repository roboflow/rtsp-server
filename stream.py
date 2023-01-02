# import necessary argumnets 
import gi
import cv2
import argparse

# import required library like Gstreamer and GstreamerRtspServer
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GObject, GLib
from roboflow import Roboflow

# Roboflow Authentication
# obtaining your API key: https://docs.roboflow.com/rest-api#obtaining-your-api-key
rf = Roboflow(api_key="API")
workspace = rf.workspace()

# # Gstreamer variables
# device_id = "rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4"
# fps = 24
# image_width = 240
# image_height = 160
# port = 8554
stream_uri = "/video_stream"

# Access output RTSP via VLC or other application
# Example RTSP output: rtsp://172.27.23.235:8554/video_stream

# getting the required information from the user # UNCOMMENT FOR ARGPARSER
parser = argparse.ArgumentParser()
parser.add_argument("--device_id", default="rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4", help="device id for the \
                video device or video file location")
parser.add_argument("--fps", default=24, help="fps of the camera", type = int)
parser.add_argument("--image_width", default=240, help="video frame width", type = int)
parser.add_argument("--image_height", default=160, help="video frame height", type = int)
parser.add_argument("--port", default=8554, help="port to stream video", type = int)
# parser.add_argument("--stream_uri", default = "/video_stream", help="rtsp video stream uri")
opt = parser.parse_args()

try:
    device_id = int(opt.device_id)
except ValueError:
    pass


# Sensor Factory class which inherits the GstRtspServer base class and add
# properties to it.
class SensorFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, **properties):
        super(SensorFactory, self).__init__(**properties)
        self.cap = cv2.VideoCapture(opt.device_id)
        self.number_frames = 0
        self.fps = opt.fps
        self.duration = 1 / self.fps * Gst.SECOND  # duration of a frame in nanoseconds
        self.launch_string = 'appsrc name=source is-live=true block=true format=GST_FORMAT_TIME ' \
                             'caps=video/x-raw,format=BGR,width={},height={},framerate={}/1 ' \
                             '! videoconvert ! video/x-raw,format=I420 ' \
                             '! x264enc speed-preset=ultrafast tune=zerolatency ' \
                             '! rtph264pay config-interval=1 name=pay0 pt=96' \
                             .format(opt.image_width, opt.image_height, self.fps)

    # method to capture the video feed from the camera and push it to the
    # streaming buffer.
    def on_need_data(self, src, length):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                # It is better to change the resolution of the camera 
                # instead of changing the image shape as it affects the image quality.
                frame = cv2.resize(frame, (opt.image_width, opt.image_height), \
                    interpolation = cv2.INTER_LINEAR)

                data = frame.tostring()
                buf = Gst.Buffer.new_allocate(None, len(data), None)
                buf.fill(0, data)
                buf.duration = self.duration
                timestamp = self.number_frames * self.duration
                buf.pts = buf.dts = int(timestamp)
                buf.offset = timestamp
                self.number_frames += 1
                frame_counter = self.number_frames
                retval = src.emit('push-buffer', buf)
                print('pushed buffer, frame {}, duration {} ns, durations {} s'.format(self.number_frames,
                                                                                       self.duration,
                                                                                       self.duration / Gst.SECOND))

                if retval != Gst.FlowReturn.OK:
                    print(retval)

                if frame_counter % 60 == 0: 

                    raw_data_location = frame
                    raw_data_extension = ".jpg"

                    # replace * with your model version number for inference
                    inference_endpoint = ["obs-3", 16]
                    upload_destination = "obs-3"

                    conditionals = {
                        "required_objects_count" : 0,
                        "required_class_count": 0,
                        "target_classes": [],
                        "minimum_size_requirement" : float('-inf'),
                        "maximum_size_requirement" : float('inf'),
                        "confidence_interval" : [10,90],
                    }

                    workspace.active_learning(raw_data_location=raw_data_location, 
                        raw_data_extension=raw_data_extension,
                        inference_endpoint=inference_endpoint,
                        upload_destination=upload_destination,
                        conditionals=conditionals,use_localhost=False)

    # attach the launch string to the override method
    def do_create_element(self, url):
        return Gst.parse_launch(self.launch_string)
    
    # attaching the source element to the rtsp media
    def do_configure(self, rtsp_media):
        self.number_frames = 0
        appsrc = rtsp_media.get_element().get_child_by_name('source')
        appsrc.connect('need-data', self.on_need_data)

# Rtsp server implementation where we attach the factory sensor with the stream uri
class GstServer(GstRtspServer.RTSPServer):
    def __init__(self, **properties):
        super(GstServer, self).__init__(**properties)
        self.factory = SensorFactory()
        self.factory.set_shared(True)
        self.set_service(str(opt.port))
        self.get_mount_points().add_factory(stream_uri, self.factory)
        self.attach(None)

# initializing the threads and running the stream on loop.
GObject.threads_init()
Gst.init(None)
server = GstServer()
loop = GLib.MainLoop()
loop.run()
