# นำเข้าโมดูลที่จำเป็น
import socket  # สำหรับการสื่อสารผ่านเครือข่าย
import threading  # สำหรับการทำงานแบบหลาย thread
import json  # สำหรับการจัดการข้อมูล JSON
import sys  # สำหรับการเข้าถึงตัวแปรและฟังก์ชันที่เกี่ยวข้องกับระบบ
import os  # สำหรับการทำงานกับระบบปฏิบัติการ
import secrets  # สำหรับการสร้างข้อมูลที่ปลอดภัยทางคริปโตกราฟี

class Node:
    def __init__(self, host, port):
        self.host = host  # กำหนด host ของโหนด
        self.port = port  # กำหนด port ของโหนด
        self.peers = []  # สร้างลิสต์ว่างสำหรับเก็บ peers
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # สร้าง socket สำหรับการสื่อสาร
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # ตั้งค่า socket ให้สามารถใช้ port ซ้ำได้
        self.transactions = []  # สร้างลิสต์ว่างสำหรับเก็บ transactions
        self.transaction_file = f"transactions_{port}.json"  # กำหนดชื่อไฟล์สำหรับบันทึก transactions
        self.wallet_address = self.generate_wallet_address()  # สร้าง wallet address

    def generate_wallet_address(self):
        # สร้าง wallet address แบบง่ายๆ โดยใช้ secrets.token_hex
        return '0x' + secrets.token_hex(20)

    def start(self):
        self.socket.bind((self.host, self.port))  # ผูก socket กับ host และ port
        self.socket.listen(1)  # เริ่มการรับฟังการเชื่อมต่อ
        print(f"Node listening on {self.host}:{self.port}")  # แสดง host และ port ที่กำลังรับฟัง
        print(f"Your wallet address is: {self.wallet_address}")  # แสดง wallet address

        self.load_transactions()  # โหลด transactions จากไฟล์

        # เริ่ม thread สำหรับการรับการเชื่อมต่อใหม่
        accept_thread = threading.Thread(target=self.accept_connections)
        accept_thread.start()

    def accept_connections(self):
        while True:
            client_socket, address = self.socket.accept()  # รับการเชื่อมต่อใหม่
            print(f"New connection from {address}")  # แสดงข้อความเมื่อมีการเชื่อมต่อใหม่

            # สร้าง thread ใหม่สำหรับจัดการการเชื่อมต่อนั้น
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_thread.start()

    def handle_client(self, client_socket):
        while True:
            try:
                data = client_socket.recv(1024)  # รับข้อมูลจาก client
                if not data:
                    break
                message = json.loads(data.decode('utf-8'))  # แปลงข้อมูลเป็น JSON
                
                self.process_message(message, client_socket)  # ประมวลผลข้อความ

            except Exception as e:
                print(f"Error handling client: {e}")  # แสดงข้อผิดพลาด
                break

        client_socket.close()  # ปิดการเชื่อมต่อ

    def connect_to_peer(self, peer_host, peer_port):
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # สร้าง socket สำหรับเชื่อมต่อกับ peer
            peer_socket.connect((peer_host, peer_port))  # เชื่อมต่อกับ peer
            self.peers.append(peer_socket)  # เพิ่ม peer ลงในรายการ peers
            print(f"Connected to peer {peer_host}:{peer_port}")  # แสดงข้อความเมื่อเชื่อมต่อสำเร็จ

            self.request_sync(peer_socket)  # ขอซิงโครไนซ์ข้อมูล

            # เริ่ม thread สำหรับจัดการการสื่อสารกับ peer นี้
            peer_thread = threading.Thread(target=self.handle_client, args=(peer_socket,))
            peer_thread.start()

        except Exception as e:
            print(f"Error connecting to peer: {e}")  # แสดงข้อผิดพลาดเมื่อเชื่อมต่อไม่สำเร็จ

    def broadcast(self, message):
        for peer_socket in self.peers:
            try:
                peer_socket.send(json.dumps(message).encode('utf-8'))  # ส่งข้อความไปยัง peer
            except Exception as e:
                print(f"Error broadcasting to peer: {e}")  # แสดงข้อผิดพลาดเมื่อส่งไม่สำเร็จ
                self.peers.remove(peer_socket)  # ลบ peer ที่มีปัญหาออกจากรายการ

    def process_message(self, message, client_socket):
        if message['type'] == 'transaction':
            print(f"Received transaction: {message['data']}")  # แสดงข้อความเมื่อได้รับ transaction
            self.add_transaction(message['data'])  # เพิ่ม transaction
        elif message['type'] == 'sync_request':
            self.send_all_transactions(client_socket)  # ส่ง transactions ทั้งหมดเมื่อได้รับคำขอซิงโครไนซ์
        elif message['type'] == 'sync_response':
            self.receive_sync_data(message['data'])  # รับข้อมูลซิงโครไนซ์
        else:
            print(f"Received message: {message}")  # แสดงข้อความที่ได้รับ

    def add_transaction(self, transaction):
        if transaction not in self.transactions:
            self.transactions.append(transaction)  # เพิ่ม transaction ลงในรายการ
            self.save_transactions()  # บันทึก transactions ลงไฟล์
            print(f"Transaction added and saved: {transaction}")  # แสดงข้อความเมื่อเพิ่ม transaction สำเร็จ

    def create_transaction(self, recipient, amount):
        transaction = {
            'sender': self.wallet_address,
            'recipient': recipient,
            'amount': amount
        }
        self.add_transaction(transaction)  # เพิ่ม transaction
        self.broadcast({'type': 'transaction', 'data': transaction})  # ส่ง transaction ไปยังทุก peer

    def save_transactions(self):
        with open(self.transaction_file, 'w') as f:
            json.dump(self.transactions, f)  # บันทึก transactions ลงไฟล์ JSON

    def load_transactions(self):
        if os.path.exists(self.transaction_file):
            with open(self.transaction_file, 'r') as f:
                self.transactions = json.load(f)  # โหลด transactions จากไฟล์
            print(f"Loaded {len(self.transactions)} transactions from file.")  # แสดงจำนวน transactions ที่โหลด

    def request_sync(self, peer_socket):
        sync_request = json.dumps({"type": "sync_request"}).encode('utf-8')
        peer_socket.send(sync_request)  # ส่งคำขอซิงโครไนซ์ไปยัง peer

    def send_all_transactions(self, client_socket):
        sync_data = json.dumps({
            "type": "sync_response",
            "data": self.transactions
        }).encode('utf-8')
        client_socket.send(sync_data)  # ส่ง transactions ทั้งหมดไปยังโหนดที่ขอซิงโครไนซ์

    def receive_sync_data(self, sync_transactions):
        for tx in sync_transactions:
            self.add_transaction(tx)  # เพิ่ม transactions ที่ได้รับจากการซิงโครไนซ์
        print(f"Synchronized {len(sync_transactions)} transactions.")  # แสดงจำนวน transactions ที่ซิงโครไนซ์

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <port>")  # แสดงวิธีใช้งานที่ถูกต้อง
        sys.exit(1)
    
    port = int(sys.argv[1])  # รับ port จาก command line argument
    node = Node("0.0.0.0", port)  # สร้างโหนดใหม่
    node.start()  # เริ่มต้นการทำงานของโหนด
    
    while True:
        print("\n1. Connect to a peer")
        print("2. Create a transaction")
        print("3. View all transactions")
        print("4. View my wallet address")
        print("5. Exit")
        choice = input("Enter your choice: ")  # รับตัวเลือกจากผู้ใช้
        
        if choice == '1':
            peer_host = input("Enter peer host to connect: ")  # รับ host ของ peer ที่ต้องการเชื่อมต่อ
            peer_port = int(input("Enter peer port to connect: "))  # รับ port ของ peer ที่ต้องการเชื่อมต่อ
            node.connect_to_peer(peer_host, peer_port)  # เชื่อมต่อกับ peer
        elif choice == '2':
            recipient = input("Enter recipient wallet address: ")  # รับ wallet address ของผู้รับ
            amount = float(input("Enter amount: "))  # รับจำนวนเงิน
            node.create_transaction(recipient, amount)  # สร้าง transaction ใหม่
        elif choice == '3':
            print("All transactions:")
            for tx in node.transactions:
                print(tx)  # แสดง transactions ทั้งหมด
        elif choice == '4':
            print(f"Your wallet address is: {node.wallet_address}")  # แสดง wallet address ของโหนดนี้
        elif choice == '5':
            break  # ออกจากลูป
        else:
            print("Invalid choice. Please try again.")  # แสดงข้อความเมื่อเลือกตัวเลือกไม่ถูกต้อง

    print("Exiting...")  # แสดงข้อความเมื่อออกจากโปรแกรม