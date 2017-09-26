.PHONY: compile test channels

compile:
	populus compile

test: compile
	pytest

channels: compile
	pytest tests/test_brass_channels.py

oracle: compile
	pytest tests/test_brass_oracle.py

batch: compile
	pytest tests/test_brass_batch.py
