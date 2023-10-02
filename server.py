import socket
import threading
import pickle
import os
import sys
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email import encoders

groups = {}
fileTransferCondition = threading.Condition()

class Group:
	def __init__(self,admin,client):
		self.admin = admin
		self.clients = {}
		self.offlineMessages = {}
		self.allMembers = set()
		self.onlineMembers = set()
		self.joinRequests = set()
		self.waitClients = {}

		self.clients[admin] = client
		self.allMembers.add(admin)
		self.onlineMembers.add(admin)

	def disconnect(self,username):
		self.onlineMembers.remove(username)
		del self.clients[username]
	
	def connect(self,username,client):
		self.onlineMembers.add(username)
		self.clients[username] = client

	def sendMessage(self,message,username):
		for member in self.onlineMembers:
			if member != username:
				self.clients[member].send(bytes(username + ": " + message,"utf-8"))

def studyChat(client, username, groupname):
	while True:
		msg = client.recv(1024).decode("utf-8")
		if msg == "/viewRequests":
			client.send(b"/viewRequests")
			client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/sendingData")
				client.recv(1024)
				client.send(pickle.dumps(groups[groupname].joinRequests))
			else:
				client.send(b"You're not an admin.")
		elif msg == "/approveRequest":
			client.send(b"/approveRequest")
			client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/proceed")
				usernameToApprove = client.recv(1024).decode("utf-8")
				if usernameToApprove in groups[groupname].joinRequests:
					groups[groupname].joinRequests.remove(usernameToApprove)
					groups[groupname].allMembers.add(usernameToApprove)
					if usernameToApprove in groups[groupname].waitClients:
						groups[groupname].waitClients[usernameToApprove].send(b"/accepted")
						groups[groupname].connect(usernameToApprove,groups[groupname].waitClients[usernameToApprove])
						del groups[groupname].waitClients[usernameToApprove]
					print("Member Approved:",usernameToApprove,"| Group:",groupname)
					client.send(b"User has been added to the group.")
				else:
					client.send(b"The user has not requested to join.")
			else:
				client.send(b"You're not an admin.")
		elif msg == "/disconnect":
			client.send(b"/disconnect")
			client.recv(1024).decode("utf-8")
			groups[groupname].disconnect(username)
			print("User Disconnected:",username,"| Group:",groupname)
			break
		elif msg == "/messageSend":
			client.send(b"/messageSend")
			message = client.recv(1024).decode("utf-8")
			groups[groupname].sendMessage(message,username)
		elif msg == "/waitDisconnect":
			client.send(b"/waitDisconnect")
			del groups[groupname].waitClients[username]
			print("Waiting Client:",username,"Disconnected")
			break
		elif msg == "/allMembers":
			client.send(b"/allMembers")
			client.recv(1024).decode("utf-8")
			client.send(pickle.dumps(groups[groupname].allMembers))
		elif msg == "/onlineMembers":
			client.send(b"/onlineMembers")
			client.recv(1024).decode("utf-8")
			client.send(pickle.dumps(groups[groupname].onlineMembers))
		elif msg == "/changeAdmin":
			client.send(b"/changeAdmin")
			client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/proceed")
				newAdminUsername = client.recv(1024).decode("utf-8")
				if newAdminUsername in groups[groupname].allMembers:
					groups[groupname].admin = newAdminUsername
					print("New Admin:",newAdminUsername,"| Group:",groupname)
					client.send(b"Your adminship is now transferred to the specified user.")
				else:
					client.send(b"The user is not a member of this group.")
			else:
				client.send(b"You're not an admin.")
		elif msg == "/whoAdmin":
			client.send(b"/whoAdmin")
			groupname = client.recv(1024).decode("utf-8")
			client.send(bytes("Admin: "+groups[groupname].admin,"utf-8"))
		elif msg == "/kickMember":
			client.send(b"/kickMember")
			client.recv(1024).decode("utf-8")
			if username == groups[groupname].admin:
				client.send(b"/proceed")
				usernameToKick = client.recv(1024).decode("utf-8")
				if usernameToKick in groups[groupname].allMembers:
					groups[groupname].allMembers.remove(usernameToKick)
					if usernameToKick in groups[groupname].onlineMembers:
						groups[groupname].clients[usernameToKick].send(b"/kicked")
						groups[groupname].onlineMembers.remove(usernameToKick)
						del groups[groupname].clients[usernameToKick]
					print("User Removed:",usernameToKick,"| Group:",groupname)
					client.send(b"The specified user is removed from the group.")
				else:
					client.send(b"The user is not a member of this group.")
			else:
				client.send(b"You're not an admin.")
		elif msg == "/fileTransfer":
			client.send(b"/fileTransfer")
			filename = client.recv(1024).decode("utf-8")
			if filename == "~error~":
				continue
			client.send(b"/sendFile")
			remaining = int.from_bytes(client.recv(4),'big')
			f = open(filename,"wb")
			while remaining:
				data = client.recv(min(remaining,4096))
				remaining -= len(data)
				f.write(data)
			f.close()
			print("File received:",filename,"| User:",username,"| Group:",groupname)
			for member in groups[groupname].onlineMembers:
				if member != username:
					memberClient = groups[groupname].clients[member]
					memberClient.send(b"/receiveFile")
					with fileTransferCondition:
						fileTransferCondition.wait()
					memberClient.send(bytes(filename,"utf-8"))
					with fileTransferCondition:
						fileTransferCondition.wait()
					with open(filename,'rb') as f:
						data = f.read()
						dataLen = len(data)
						memberClient.send(dataLen.to_bytes(4,'big'))
						memberClient.send(data)
			client.send(bytes(filename+" successfully sent to all online group members.","utf-8"))
			print("File sent",filename,"| Group: ",groupname)
			os.remove(filename)
		elif msg == "/sendFilename" or msg == "/sendFile":
			with fileTransferCondition:
				fileTransferCondition.notify()

def send_otp( email , otp ) :
    # creates SMTP session
	s = smtplib.SMTP('smtp.gmail.com', 587)
 
	# start TLS for security
	s.starttls()
 
	# Authentication
	s.login(" stealthsamp@gmail.com", "kbgeahjzhkimvata")

 
	# message to be sent
	message = otp 
 
	# sending the mail
	s.sendmail("stealthsamp@gmail.com", email , message)
	
 
	# terminating the session
	s.quit()

def authenticate_user(usr, pswd):
    # Connect to the database
    print("authenticate success")
    conn = sqlite3.connect('user_credentials.db')
    cursor = conn.cursor()

    # Define the SQL query to retrieve the user with the given username and activation is True
    query = '''
    SELECT username, password
    FROM user_credentials
    WHERE username = ? AND password = ?
    '''

    # Execute the query with username and password as parameters
    cursor.execute(query, (usr, pswd))
    user = cursor.fetchone()  # Fetch the first matching row

    # Close the database connection
    conn.close()

    return user is not None
		
def handshake(client):
	while(1):
		msg = client.recv(1024).decode("utf-8") 
		if msg == "/Registration" : 
			client.send(b"/Registration")
			username = client.recv(1024).decode("utf-8") 
			client.send(b"uname")
			password = client.recv(1024).decode("utf-8") 
			client.send(b"pass")
			email = client.recv(1024).decode("utf-8") 
			client.send(b"mail")
			otp = client.recv(1024).decode("utf-8")
			print("Username: ",username, "\nPassword: ",password, "\nEmail: ",email,"\nOTP: ",otp)
			send_otp( email , otp )
			client.send(b"/OTPverification")
			# client.recv(1024).decode("utf-8")
			resp = client.recv(1024).decode("utf-8")
			if resp == "/Success" :
				# Connect to the database
				conn = sqlite3.connect('user_credentials.db')
				cursor = conn.cursor()
				
				try:	
					activation = True
					insert_data_sql = '''
					INSERT INTO user_credentials (username, password, email, activation)
					VALUES (?, ?, ?, ?)
					'''
					cursor.execute(insert_data_sql, (username, password, email, activation))
					# Commit the changes to the database
					conn.commit()
					print("Data inserted into user_credentials.db successfully.") 
				except Exception as e:
					print(f"Error: {e}")
				finally:
					# Close the database connection
					conn.close()
			else:
				print("Invalid OTP")
		elif msg == "/Login" :
			client.send(b"/Login")
			username = client.recv(1024).decode("utf-8")
			client.send(b"/uname")
			password = client.recv(1024).decode("utf-8")
			if authenticate_user( username, password):
				client.send(b"/Success")
				print(username, "is online")
			else:
				client.send(b"/Failed")
		elif msg == "/finish":
			break;
	
	username = client.recv(1024).decode("utf-8")
	client.send(b"/sendGroupname")
	groupname = client.recv(1024).decode("utf-8")
	if groupname in groups:
		if username in groups[groupname].allMembers:
				groups[groupname].connect(username,client)
				client.send(b"/ready")
				print("User Connected:",username,"| Group:",groupname)
		else:
				groups[groupname].joinRequests.add(username)
				groups[groupname].waitClients[username] = client
				groups[groupname].sendMessage(username+" has requested to join the group.","Group session")
				client.send(b"/wait")
				print("Join Request:",username,"| Group:",groupname)
		threading.Thread(target=studyChat, args=(client, username, groupname,)).start()
	else:
		groups[groupname] = Group(username,client)
		threading.Thread(target=studyChat, args=(client, username, groupname,)).start()
		client.send(b"/adminReady")
		print("New Group:",groupname,"| Admin:",username)

def main():
	if len(sys.argv) < 3:
		print("USAGE: python server.py <IP> <Port>")
		print("EXAMPLE: python server.py localhost 8000")
		return
	listenSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	listenSocket.bind((sys.argv[1], int(sys.argv[2])))
	listenSocket.listen(10)
	print("App Server running")
	while True:
		client,_ = listenSocket.accept()
		threading.Thread(target=handshake, args=(client,)).start()

if __name__ == "__main__":
	main()
   
