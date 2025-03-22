import os
import threading
import socket
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from flask import Flask, send_from_directory, Response, request
from werkzeug.serving import make_server


class FileSharerApp:
    def __init__(self, root):
        self.root = root
        self.server = None
        self.server_thread = None
        self.shared_folder = os.getcwd()
        self.running = False
        self.current_connections = set()

        self.setup_gui()
        self.update_ip()

    def setup_gui(self):
        self.root.title("局域网文件分享工具")
        self.root.geometry("800x600")

        # 控制面板
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X)

        # 文件夹选择
        self.folder_btn = ttk.Button(
            control_frame,
            text="选择文件夹",
            command=self.select_folder
        )
        self.folder_btn.pack(side=tk.LEFT, padx=5)

        # 端口设置
        ttk.Label(control_frame, text="端口:").pack(side=tk.LEFT, padx=5)
        self.port_entry = ttk.Entry(control_frame, width=8)
        self.port_entry.insert(0, "5555")
        self.port_entry.pack(side=tk.LEFT, padx=5)

        # IP显示
        self.ip_label = ttk.Label(control_frame, text="访问地址：")
        self.ip_label.pack(side=tk.LEFT, padx=20)

        # 控制按钮
        self.start_btn = ttk.Button(
            control_frame,
            text="启动服务",
            command=self.toggle_server,
            style="Toggle.TButton"
        )
        self.start_btn.pack(side=tk.RIGHT, padx=5)

        # 日志区域
        self.log = tk.Text(self.root, state='disabled')
        self.log.pack(expand=True, fill='both', padx=10, pady=10)

        # 状态栏
        self.status = ttk.Label(self.root, text="已停止", foreground="red")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.shared_folder = folder
            self.log_message(f"共享目录设置为：{folder}")

    def update_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            self.ip_label.config(text=f"访问地址：http://{ip}:{self.port_entry.get()}")
        except Exception as e:
            self.ip_label.config(text="无法获取IP地址")
        finally:
            s.close()

    def toggle_server(self):
        if self.running:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        port = self.port_entry.get()
        if not port.isdigit():
            messagebox.showerror("错误", "端口号必须是数字")
            return

        self.app = Flask(__name__)
        self.setup_routes()

        try:
            self.server = make_server('0.0.0.0', int(port), self.app)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
        except OSError as e:
            messagebox.showerror("错误", f"端口 {port} 被占用")
            return

        self.running = True
        self.start_btn.config(text="停止服务")
        self.status.config(text="运行中", foreground="green")
        self.log_message(f"服务已启动，端口：{port}")
        self.update_ip()

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server_thread.join()
        self.running = False
        self.start_btn.config(text="启动服务")
        self.status.config(text="已停止", foreground="red")
        self.log_message("服务已停止")

    def setup_routes(self):
        @self.app.route('/')
        def index():
            return self.generate_file_list()

        @self.app.route('/<path:filename>')
        def serve_file(filename):
            client_ip = request.remote_addr
            self.current_connections.add(client_ip)
            self.log_message(f"新连接：{client_ip} -> {filename}")

            if filename.endswith(('.mp4', '.mkv', '.avi')):
                return self.video_stream(filename)

            return send_from_directory(self.shared_folder, filename)

    def video_stream(self, filename):
        path = os.path.join(self.shared_folder, filename)
        file_size = os.path.getsize(path)
        start = 0
        end = file_size - 1

        range_header = request.headers.get('Range', None)
        if range_header:
            start, end = self.parse_range_header(range_header, file_size)

        def generate():
            with open(path, 'rb') as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk_size = min(4096, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            'Content-Type': 'video/mp4',
            'Accept-Ranges': 'bytes',
            'Content-Length': end - start + 1,
            'Content-Range': f'bytes {start}-{end}/{file_size}'
        }

        return Response(generate(), 206 if range_header else 200, headers=headers)

    def parse_range_header(self, range_header, file_size):
        bytes_unit, _, range_spec = range_header.partition('=')
        start, end = range_spec.split('-')
        start = int(start) if start else 0
        end = int(end) if end else file_size - 1
        return start, min(end, file_size - 1)

    def generate_file_list(self):
        files = os.listdir(self.shared_folder)
        html = ['<html><head><meta charset="UTF-8"></head><body>']
        html.append('<h1>共享文件列表</h1>')
        html.append('<ul>')
        for f in files:
            if os.path.isfile(os.path.join(self.shared_folder, f)):
                html.append(f'<li><a href="{f}">{f}</a></li>')
        html.append('</ul></body></html>')
        return '\n'.join(html)

    def log_message(self, msg):
        self.log.config(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.config(state='disabled')


if __name__ == "__main__":
    root = tk.Tk()
    app = FileSharerApp(root)
    root.mainloop()
