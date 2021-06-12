#!/usr/bin/python3.7

import json
import boto3
import requests
import os
import shutil

TENANT_ID = "XXXXX";
APPCLIENT_ID = "XXXX";
APPSECRET = "XXXXXX";
FILES_ROOT_DIR = "/home/steve/o365/OneDrive Backup 2";

CHILD_TYPE_FILE = 1
CHILD_TYPE_DIR = 0

AWS_KEY = "XXXXXX";
AWS_SECRET = "XXXXXX";
#S3_BUCKET = "XXXXX";
S3_BUCKET = "ZZZZ";
ONEDRIVE_ROOT = "OneDriveRoot";

msft_graph_endpoints = {
                        "users": "https://graph.microsoft.com/v1.0/users",
                        "messages": "https://graph.microsoft.com/v1.0/me/messages"
                        }
token = "";

class new_tenant:
	aad_users = [];
	tenant_id = "";
	app_id = "";
	app_secret = "";
	token = "";
	sessionobj = "";
	s3_bucket = "" 
	aws_key = "";
	aws_secret = ""
	onedrive_root = "";
	################################################################
	def __init__(self, tenant_id, app_id, app_secret, bucket, key, secret, root):
		self.tenant_id = tenant_id; 
		self.app_id = app_id;
		self.app_secret = app_secret; 
		self.sessionobj = requests.Session();
		self.s3_bucket = bucket;
		self.aws_key = key;
		self.aws_secret = secret;
		self.onedrive_root = root;
	################################################################

class aad_user:
	user_id = "";
	display_name =  "";
	email_address = "";
	#####################################
	def __init__(self, id, name, email):
		self.user_id = id;
		self.display_name = name;
		self.email_address = email;
	######################################


class child:
	child_id = "";
	child_name = "";
	child_url = "";
	### child_type:  0=folder, 1=file
	# defines:  CHILD_TYPE_FILE = 1
	#           CHILD_TYPE_DIR = 0
	child_type = "";
	# child_path comes from parentReference in jSON
	child_path = "";
	#####################################
	def __init__(self, id, name, url, type, path):
		self.child_id = id;
		self.child_name = name;
		self.child_url = url;
		self.child_type = type; 
		self.child_path = path;
		#self.child_stepchildren_count = count;
	####################################



##########################################################################################################
# our main()
##########################################################################################################
def main():

	os.system('clear');
	print("Hello World");

	our_tenants = []; 
	our_tenants.append( new_tenant(TENANT_ID, APPCLIENT_ID, APPSECRET, S3_BUCKET, AWS_KEY, AWS_SECRET, ONEDRIVE_ROOT ) );
	root_children = [];

	s3 = boto3.client('s3');

	make_local_dir(FILES_ROOT_DIR);
	change_local_dir(FILES_ROOT_DIR);

	for tenant in our_tenants:
		# get auth token and define token in passed in tenant object
		if not get_token(tenant): print("Error No Token"); return; 
		# get list of object user for tenant and define in passed in tenant object
		if not get_users(tenant): print("Error on get_users"); return; 
		print("User Count:", len(tenant.aad_users))

		# create tenant sub dir
		make_local_dir(tenant.tenant_id)
		change_local_dir(tenant.tenant_id)

		for account in tenant.aad_users:
			print("user email:", account.email_address)
			print("user id:", account.user_id)
			get_root_children_list(tenant, account, root_children)
			#make user account subdir
			make_local_dir(account.user_id);
			change_local_dir(account.user_id);
			# make onedrive_root subdir
			make_local_dir(tenant.onedrive_root);
			change_local_dir(tenant.onedrive_root);
			# build list of childs in root
			get_children(tenant, account, root_children, s3)
			# backup to the prev dir to be ready for next interation of loop
			os.chdir("../../");
	# backup to the prev dir to be ready for next interation of loop
	os.chdir("../");
	# exit main() w/ true 
	return 1; 
#############################################################################################################




def s3_make_dir(tenant, account, s3, child):
	s3_obj_name = tenant.tenant_id + "/" + account.user_id + "/" + child.child_path + "/" +  child.child_name + "/";
	#print("s3objname:", s3_obj_name);
	make_local_dir("/tmp/o365/")
	fname = "/tmp/o365/" + child.child_name;
	fp = open(fname, "wb");
	fp.close();
	response = s3.upload_file(fname, tenant.s3_bucket, s3_obj_name)
	os.remove(fname);

############################################################################################################
def get_children(tenant, account, children_list, s3):
	session = tenant.sessionobj;
	stepchildren = [];
	for child in children_list:
		if child.child_type is CHILD_TYPE_FILE:
			dl_child(tenant, account, s3, child)
		elif child.child_type is CHILD_TYPE_DIR:
			s3_make_dir(tenant, account, s3, child);
			make_local_dir(child.child_name);
			change_local_dir(child.child_name);
			get_step_children_list(tenant, account, child.child_id, stepchildren)
			get_children(tenant, account, stepchildren, s3);
			change_local_dir("../");
############################################################################################################


########################################################
def make_local_dir(dir):
	if not os.path.exists(dir):
		try: os.mkdir(dir)
		except: print("Error creating dir:", dir);
########################################################

########################################################
def change_local_dir(dir):
	if os.path.exists(dir):
		try: os.chdir(dir)
		except: print("Cannot change to dir:", dir);
	else:
		print("dir does not exist:",dir);
########################################################


##########################################################################################################
# void dl_child(child)
# only passing child
# we dont use session object for this request because
# msft graph api doesnt like when the requests has the same http headers
# that is stored in session object used in the other request. Kind of odd 
##########################################################################################################
def dl_child(tenant, account, s3, child):
	#print("endpoint:", child.child_url)
	#if not os.path.exists(child.child_name):
	localfile = open(child.child_name, "wb");
	download = requests.get(child.child_url);
	localfile.write(download.content)
	localfile.close();
	print("child.child_path:",child.child_path,child.child_name);
	print("child.child_path len:", len(child.child_path));
	s3_obj_name = tenant.tenant_id + "/" + account.user_id + "/" + child.child_path + "/" + child.child_name;
	print("s3objname:", s3_obj_name);
	response = s3.upload_file(child.child_name, tenant.s3_bucket, s3_obj_name)
##########################################################################################################


##########################################################################################################
# get_step_children_list(session, account, item_id, list)
# goal is to merge this function with get_root_children_list()
##########################################################################################################
def get_step_children_list(tenant, account, item_id, list):
	list.clear();
	endpoint = "https://graph.microsoft.com/v1.0/users/" + account.user_id + "/drive/items/" + item_id + "/children"
	response = tenant.sessionobj.get(endpoint);
	if response.status_code is not 200:  return 0;
	json = response.json();
	for __child in json["value"]:
		print(__child, "\r\n ");
		if "file" in __child:
			child_url = __child["@microsoft.graph.downloadUrl"];
			child_type = CHILD_TYPE_FILE;
		elif "folder" in __child:
			child_url = "";
			child_type = CHILD_TYPE_DIR; 
			#child_stepchildren_count = __child["folder"]["childCount"];
		child_id = __child["id"];
		child_name = __child["name"];
		child_path = parse_path(__child, tenant);
		list.append( child(child_id, child_name, child_url, child_type, child_path) );
	return;
##########################################################################################################

##########################################################################################################
#
##########################################################################################################
def get_root_children_list(tenant, account, list):

	list.clear();
	endpoint = "https://graph.microsoft.com/v1.0/users/" + account.user_id + "/drive/root/children"
	session = tenant.sessionobj;
	response = session.get(endpoint);
	if response.status_code is not 200:  return 0;
	json = response.json();
	for __child in json["value"]:
		print(__child, "\r\n ");
		if "file" in __child:
			child_url = __child["@microsoft.graph.downloadUrl"];
			child_type = CHILD_TYPE_FILE;
		elif "folder" in __child:
			child_url = "";
			child_type = CHILD_TYPE_DIR; 
		child_path = parse_path(__child, tenant)
		child_id = __child["id"];
		child_name = __child["name"];
		list.append( child(child_id, child_name, child_url, child_type, child_path) );
	return
##########################################################################################################


##########################################################################################################
def parse_path(child, tenant):
	parsed = [];
	if "path" in child["parentReference"]:
		parsed = child["parentReference"]["path"].split(":");
		print("parsed:", parsed);
		if parsed[1] == '':
			parsed[1] = tenant.onedrive_root;
		else:
			parsed[1] = tenant.onedrive_root + parsed[1]

		return parsed[1];
##########################################################################################################



##########################################################################################################
#  send a request to API for all users and retur 0 on error or 1 on ok. 
##########################################################################################################
def get_users(tenant):
	session = tenant.sessionobj;
	endpoint = msft_graph_endpoints["users"]
	response = session.get(endpoint)
	if response.status_code is not 200:
		return 0;
	json = response.json(); 
	for user in json["value"]:
		tenant.aad_users.append( aad_user(user["id"],user["displayName"],user["mail"]))

	return 1; 
##########################################################################################################




##########################################################################################################
# send HTTP POST to endpoint.  ken as long as https response code is 200 (ok). else return 0
# uses https requests python module
# see microsoft graph API authentication docs
##########################################################################################################
def get_token(tenant):

	endpoint_base = "https://login.microsoftonline.com/";
	#endpoint_url = endpoint_base + tenant_id + "/oauth2/v2.0/token";
	endpoint_url = endpoint_base + tenant.tenant_id + "/oauth2/v2.0/token";
	http_headers = {'Host': 'login.microsoftonline.com', 'Content-Type': 'application/x-www-form-urlencoded'};
	request_data = ("client_id=" + tenant.app_id,
        	       "&scope=https://graph.microsoft.com/.default",
                        "&client_secret=" + tenant.app_secret,
                        "&grant_type=client_credentials"
                        )
	session = tenant.sessionobj;
	# make one long string from array to pass to function
	data_string = "";
	for data in request_data:
		data_string = data_string + data;

	response = session.post(endpoint_url, headers = http_headers, data=data_string);
	if response.status_code is not 200:
		return 0;

	# extract token and update http headers in session object
	json = response.json();
	token = json["access_token"];
	session.headers.update({'Authorization': 'Bearer ' + token, 'Host': 'graph.microsoft.com'})
	tenant.token = token; 

	return 1; 

##########################################################################################################



##########################################################################################################
# program counter starts here
##########################################################################################################
main()









'''
##########################################################################################################
#
##########################################################################################################
def get_email(user_id):

        response = get_request("https://graph.microsoft.com/v1.0/users/" + user_id + "/messages");
        print(response.status_code);
        if response.status_code is not 200:
                        return 1;

        json = response.json();
        print("json type is:")
        print(type(json))
        print("json length :")
        print(len(json))

        all_emails = json["value"];
        print ("all_emails TYPE IS:")
        print(type(all_emails))
        print("all_emails  length :")
        print(len(all_emails))
        for email in all_emails:
                print("this email is type:")
                print(type(email))
                print("this email length is:")
                print(len(email))
                for key, value  in email.items():
                        print(key, ":", value);
                print("------")
'''
