.PHONY: compile test channels concent batch deploy

compile:
	populus compile

test: compile
	pytest

channels: compile
	pytest tests/test_brass_channels.py

concent: compile
	pytest tests/test_brass_concent.py

batch: compile
	pytest tests/test_brass_batch.py

deploy:
	python3 deploy.py
