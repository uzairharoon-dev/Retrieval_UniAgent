FROM uniagent-task1-runner:baseline

WORKDIR /app
COPY baseline.py fusion.py fusion_system.py representations.py representation_system.py german-stopwords.txt german-stopwords.NOTICE test_baseline.py test_token_length.py test_fusion.py test_representations.py /app/
RUN PYTHONPATH=. pytest .
ENTRYPOINT ["python3", "/app/baseline.py"]
