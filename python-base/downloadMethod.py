#!/usr/bin/python
def downloadMethod1():
	import urllib
	print "downloading with urllib"
	url = "https://github.com/chenqiangzhishen/Algorithms/blob/master/sorts/heapSort/heapSort.py"
	urllib.urlretrieve(url, "heapSort.py")

def downloadMethod2():
	import urllib2
	print "downloading with urllib2"
	url = "https://github.com/chenqiangzhishen/Algorithms/blob/master/sorts/heapSort/heapSort.py"
	f = urllib2.urlopen(url)
	data = f.read()
	with open("some.file", "wb")as code:
		code.write(data)

def downloadMethod3():
	import requests 
	print "downloading with requests"
	url = "https://github.com/chenqiangzhishen/Algorithms/blob/master/sorts/heapSort/heapSort.py"
	r = requests.get(url);
	with open("f3", "wb") as code:
		code.write(r.content)

def main():
	#downloadMethod1()
	#downloadMethod2()
	downloadMethod3()

if __name__ == "__main__":
	main()	
