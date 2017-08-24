.PHONY: compile test

compile:
	populus compile

test: compile
	pytest
