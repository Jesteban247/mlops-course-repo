from locust import HttpUser, between, task

PAYLOAD = {'bed': 3, 'bath': 2, 'acre_lot': 0.23, 'house_size': 1837,
           'brokered_by': 33714, 'street': 1758218, 'city': 'East Windsor',
           'state': 'Connecticut', 'zip_code': 6016}


class PropertyUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def predict(self):
        with self.client.post('/predict', json=PAYLOAD, headers={'Connection': 'close'},
                              timeout=30, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f'HTTP {response.status_code}')
                return
            try:
                data = response.json()
                if not all(key in data for key in ('prediction', 'pod', 'model_version')):
                    raise ValueError('Missing prediction, pod or model version')
            except ValueError as exc:
                response.failure(str(exc))
