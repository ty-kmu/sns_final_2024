import socket
import threading
import tkinter as tk
from tkinter import colorchooser, simpledialog, messagebox
import json
import queue


class DrawingClient:
    def __init__(self):
        self.message_queue = queue.Queue()
        self.setup_gui_initial()

        if not self.nickname:
            self.root.destroy()
            return

        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect(('localhost', 3000))
        except Exception as e:
            messagebox.showerror("연결 오류", f"서버 연결 실패: {e}")
            self.root.destroy()
            return

        self.setup_gui_main()
        self.setup_network()
        self.process_message_queue()
        self.root.mainloop()

    def setup_gui_initial(self):
        self.root = tk.Tk()
        self.root.title("그림판 & 채팅")
        self.root.withdraw()
        self.nickname = simpledialog.askstring("닉네임", "닉네임을 입력하세요:")
        self.root.deiconify()

    def setup_gui_main(self):
        # 그림판 프레임
        self.draw_frame = tk.Frame(self.root)
        self.draw_frame.pack(side=tk.LEFT, padx=5)

        self.canvas = tk.Canvas(
            self.draw_frame, width=600, height=400, bg='white')
        self.canvas.pack()

        # 도구 프레임
        self.tool_frame = tk.Frame(self.draw_frame)
        self.tool_frame.pack()

        self.color_button = tk.Button(
            self.tool_frame, text="색상 선택", command=self.choose_color)
        self.color_button.pack(side=tk.LEFT, padx=5)

        self.clear_button = tk.Button(
            self.tool_frame, text="지우기", command=self.clear_canvas)
        self.clear_button.pack(side=tk.LEFT, padx=5)

        # 채팅 프레임
        self.chat_frame = tk.Frame(self.root)
        self.chat_frame.pack(side=tk.RIGHT, padx=5)

        self.chat_box = tk.Text(self.chat_frame, height=20, width=30, wrap="word")
        self.chat_box.config(state="disabled")
        self.chat_box.pack()
        
        # 위치 설정
        self.chat_box.tag_configure("left", justify="left", foreground="black")
        self.chat_box.tag_configure("right", justify="right", foreground="grey")
        self.chat_box.tag_configure("center", justify="center", foreground="blue")

        self.msg_frame = tk.Frame(self.chat_frame)
        self.msg_frame.pack(fill=tk.X, padx=5)

        self.msg_entry = tk.Entry(self.msg_frame)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.msg_entry.bind('<Return>', lambda e: self.send_message())

        self.send_button = tk.Button(
            self.msg_frame, text="전송", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT)

        # 그리기 이벤트
        self.canvas.bind('<B1-Motion>', self.paint)
        self.canvas.bind('<ButtonRelease-1>', self.reset_position)
        self.canvas.bind('<Button-1>', self.set_position)
        self.current_color = '#000000'
        self.line_width = 2  # 선 굵기 설정

        # 종료 이벤트
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def process_message_queue(self):
        # 메시지 큐 처리
        try:
            while not self.message_queue.empty():
                data = self.message_queue.get_nowait()
                if isinstance(data, dict):
                    if data['type'] == 'line':
                        # 선 그리기 데이터 처리
                        self.canvas.create_line(
                            data['x1'], data['y1'],
                            data['x2'], data['y2'],
                            fill=data['color'],
                            width=data['width'],
                            smooth=True,
                            capstyle=tk.ROUND,
                            splinesteps=36
                        )
                    elif data['type'] == 'chat':
                        self.chat_box.config(state="normal")
                        self.chat_box.insert(tk.END, data['message'] + '\n', 'left')
                        self.chat_box.config(state="disabled")
                        self.chat_box.see(tk.END)
                    elif data['type'] == 'join_exit':
                        self.chat_box.config(state="normal")
                        self.chat_box.insert(tk.END, data['message'] + '\n', 'center')
                        self.chat_box.config(state="disabled")
                        self.chat_box.see(tk.END)
                    elif data['type'] == 'clear':
                        self.clear_canvas()
                else:
                    self.chat_box.insert(tk.END, str(data) + '\n')
                    self.chat_box.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(10, self.process_message_queue)

    def clear_canvas(self):
        # 캔버스 지우기
        self.canvas.delete("all")
        data = {
            'type': 'clear'
        }
        self.send_data(data)

    def send_data(self, data):
        # 데이터 전송
        try:
            self.client.send(json.dumps(data).encode('utf-8'))
        except Exception as e:
            print(f"전송 오류: {e}")

    def receive(self):
        while True:
            try:
                data = self.client.recv(1024).decode('utf-8')
                if not data:
                    break

                if data == 'NICK':
                    self.client.send(self.nickname.encode('utf-8'))
                else:
                    try:
                        data = json.loads(data)
                        self.message_queue.put(data)
                    except json.JSONDecodeError:
                        self.message_queue.put(data)
            except Exception as e:
                print(f"수신 오류: {e}")
                break

    def setup_network(self):
        # 수신 스레드 시작
        self.receive_thread = threading.Thread(target=self.receive)
        self.receive_thread.daemon = True  # 메인 스레드 종료시 같이 종료되도록 설정
        self.receive_thread.start()

    def set_position(self, event):
        # 마우스 클릭 시 시작 위치 설정
        self.last_x = event.x
        self.last_y = event.y

    def reset_position(self, event):
        # 마우스 릴리즈 시 위치 초기화
        self.last_x = None
        self.last_y = None

    def paint(self, event):
        # 선 그리기
        if self.last_x and self.last_y:
            x, y = event.x, event.y
            # 현재 캔버스에 선 그리기
            self.canvas.create_line(
                self.last_x, self.last_y, x, y,
                fill=self.current_color,
                width=self.line_width,
                smooth=True,
                capstyle=tk.ROUND,
                splinesteps=36
            )

            # 데이터 전송
            data = {
                'type': 'line',
                'x1': self.last_x,
                'y1': self.last_y,
                'x2': x,
                'y2': y,
                'color': self.current_color,
                'width': self.line_width
            }
            self.send_data(data)

            # 현재 위치를 다음 선의 시작점으로 설정
            self.last_x = x
            self.last_y = y

    def choose_color(self):
        try:
            color = colorchooser.askcolor(title="색상 선택")[1]
            if color:
                self.current_color = color
        except Exception as e:
            print(f"색상 선택 오류: {e}")

    def send_message(self):
        try:
            message = self.msg_entry.get().strip()
            if message:
                # 메시지 데이터 생성
                data = {
                    'type': 'chat',
                    'message': f"{self.nickname}: {message}"
                }

                # 서버로 전송
                self.client.send(json.dumps(data).encode('utf-8'))

                # 내 화면에도 즉시 표시
                self.chat_box.config(state="normal")
                self.chat_box.insert(tk.END, message + '\n', 'right')
                self.chat_box.config(state="disabled")
                self.chat_box.see(tk.END)

                # 입력창 비우기
                self.msg_entry.delete(0, tk.END)
        except Exception as e:
            print(f"메시지 전송 오류: {e}")

    def on_closing(self):
        # 창 종료시 처리
        try:
            self.client.close()
            self.root.destroy()
        except Exception as e:
            print(f"종료 오류: {e}")


if __name__ == "__main__":
    client = DrawingClient()
