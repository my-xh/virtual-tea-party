import socket, asyncore
from asyncore import dispatcher
from asynchat import async_chat

PORT = 8080
NAME = 'TestChat'


class ChatSession(async_chat):
    """聊天会话类"""

    def __init__(self, server: 'ChatServer', sock: 'socket.socket'):
        super().__init__(sock)
        self.set_terminator(b'\r\n')
        self.server = server
        self.data: list[bytes] = []
        # 问候语
        self.push(f'Welcome to {self.server.name}!\r\n'.encode())

    def handle_close(self):
        super().handle_close()
        self.server.disconnect(self)

    def collect_incoming_data(self, data: bytes):
        self.data.append(data)

    def found_terminator(self):
        line = b''.join(self.data)
        self.data = []
        self.server.broadcast(line, sender=self)


class ChatServer(dispatcher):
    """聊天服务器"""

    def __init__(self, port: int, name: str):
        super().__init__()
        self.name = name
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(('', port))
        self.listen(5)
        self.sessions: list['ChatSession'] = []

    def handle_accept(self):
        conn, addr = self.accept()
        self.sessions.append(ChatSession(self, conn))

    def disconnect(self, session: 'ChatSession'):
        self.sessions.remove(session)

    def broadcast(self, data: bytes, sender=None):
        for session in self.sessions:
            if session is sender:
                continue
            session.push(data + b'\r\n')


if __name__ == '__main__':
    s = ChatServer(PORT, NAME)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
