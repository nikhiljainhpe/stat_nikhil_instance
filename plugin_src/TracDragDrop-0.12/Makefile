.PHONY : all extract compile

python ?= python

all : compile

extract :
	$(python) setup.py extract_messages extract_messages_js

compile :
	$(python) setup.py compile_catalog compile_catalog_js generate_messages_js
