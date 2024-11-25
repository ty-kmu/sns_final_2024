import socket
import threading
import json


class DrawingServer:
    def __init__(self, host='localhost', port=3000):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen()
        self.clients = []
        self.nicknames = []
        print("서버가 시작되었습니다...")

    def broadcast(self, message, sender=None):
        # 모든 클라이언트에게 메시지 전송 (sender 제외)
        for client in self.clients:
            if client != sender:  # sender에게는 다시 보내지 않음
                try:
                    client.send(message)
                except:
                    self.remove_client(client)

    def remove_client(self, client):
        # 클라이언트 제거 처리
        if client in self.clients:
            index = self.clients.index(client)
            self.clients.remove(client)
            client.close()
            nickname = self.nicknames[index]
            self.nicknames.remove(nickname)

            exit_message = {
                    'type': 'join_exit',
                    'message': f"{nickname}님이 퇴장하셨습니다."
                }
            self.broadcast(json.dumps(exit_message).encode('utf-8'))
            
            print(f"{nickname} 연결 종료")

    def handle_client(self, client, nickname):
        while True:
            try:
                message = client.recv(1024)
                if not message:
                    break

                data = json.loads(message.decode('utf-8'))
                if data['type'] in ['line', 'chat', 'clear']:
                    self.broadcast(message, client)

            except json.JSONDecodeError:
                self.broadcast(message)
            except:
                self.remove_client(client)
                break


    def start(self):
        while True:
            try:
                client, address = self.server.accept()
                print(f"새로운 연결: {str(address)}")

                # 닉네임 요청
                client.send('NICK'.encode('utf-8'))
                nickname = client.recv(1024).decode('utf-8')
                
                self.clients.append(client)
                self.nicknames.append(nickname)

                # 입장 메시지 브로드캐스트
                print(f"닉네임: {nickname}")
                join_message = {
                    'type': 'join_exit',
                    'message': f"{nickname}님이 입장하셨습니다!"
                }
                self.broadcast(json.dumps(join_message).encode('utf-8'))

                # 클라이언트 처리 스레드 시작
                thread = threading.Thread(
                    target=self.handle_client, args=(client, nickname))
                thread.daemon = True
                thread.start()

            except Exception as e:
                print(f"연결 처리 중 오류 발생: {e}")
                continue


if __name__ == "__main__":
    server = DrawingServer()
    server.start()
