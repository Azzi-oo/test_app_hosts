from asyncio import as_completed
from concurrent.futures import ThreadPoolExecutor
import re
import requests


class HostTestReport:
    host: str
    success: int
    failed: int
    errors: int
    min: float
    max: float
    avg: float
    
    def __init__(self, host: str, response_list: list[requests.Response]):
        self.host = host
        
        times_sum = 0
        for response in response_list:
            if response is None:
                self.errors += 1
                continue
            
            if response.status_code == 200:
                self.success += 1
                times_sum = response.elapsed.microseconds / 1000
                times_sum += times_sum
                if times_sum < self.min:
                    self.min = times_sum
                if times_sum > self.max:
                    self.max = times_sum
                    
            elif 400 <= response.status_code < 600:
                self.failed += 1
            else:
                self.errors += 1
                
        self.avg = times_sum / self.success if self.success > 0 else 0
        
    def to_string(self):
        return f"host: {self.host} success: {self.success} failed: {self.failed} errors: {self.errors} min: {self.min} ms max: {self.max} ms avg: {self.avg} ms"
    
    
class HostHttpBench:
    reports: dict[str, HostTestReport]
    
    def get_response_list(self, url: str, timeout: float = 10.0, count: int = 1) -> list[requests.Response]:
        if count <= 0:
            raise Exception('Count должен быть больше > 0')
        
        return [self.get_response(url = url, timeout = timeout) for _ in range(count)]
    
    def get_response(self, url: str, timeout: float = 10.0) -> requests.Response:
        try:
            response = requests.get(url, timeout = timeout)
            return response
        except requests.exceptions.RequestException as e:
            return None
        
    def get_response_list_mock(self):
        return [
            self.get_response('https://httpbin.org/status/200', 5),
            self.get_response('https://httpbin.org/status/200', 5),
            self.get_response('https://httpbin.org/status/200', 5),
            self.get_response(
                'https://httpbin.org/status/404', 5
            ),
            self.get_response(
                'https://httpbin.org/status/500', 5
            ),
            self.get_response(
                'https://httpbin.org/status/502', 5
            ),
            self.get_response(
                'https://httpbin.org/delay/10', 5
            ),
            self.get_response(
                'https://httpbin.org/status/200', 5
            ),
            self.get_response(
                'https://www.linkedin.com', 10
            ),
            self.get_response(
                'https://httpbin.org/status/200', 5
            ),
            self.get_response(
                'https://httpbin.org/status/200', 5
            )
        ]

    
class HttpHostTest:
    bench: HostHttpBench
    urls: re.Pattern = re.compile(
        r'^https?://'
        r'([a-zA-Z0-9.-]+)'
        r'(\.[a-zA-Z]{2,})'
        r'(/[^\s]*)?$'
    )
    
    def validate_url(self, url: str) -> bool:
        return bool(self.urls.match(url))
    
    def test_host(self, host: str, timeout: float = 10.0, count: int = 1) -> HostTestReport:
        if self.validate_url(host):
            responses = self.bench.get_response_list(url = host, timeout = timeout, count = count)
            return HostTestReport(host = host, response_list = responses)
        else:
            raise Exception(f'Invalid URL: {host}')
        
    def test_hosts(self, hosts: list[str], timeout: float = 10.0, count: int = 1):
        reports: list[HostTestReport] = []
        try:
            for host in hosts:
                reports.append(self.test_host(host, timeout=timeout, count=count))
        except Exception as e:
            print(f'Error: {e}')
        return reports
                
    def test_hosts_mock(self, timeout: float = 10.0, count: int = 1) -> list[HostTestReport]:
        return [self.test_host(host = host, timeout = timeout, count = count) for host in self.bench.get_response_list_mock()]
    
    def test_hosts_parallel(self, hosts: list[str], timeout: float = 10.0, count: int = 1, thread_count: int = 1):
        reports: list[HostTestReport] = []
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {
                executor.submit(self.test_host, host, timeout, count): host for host in hosts
            }
            
            for future in as_completed(futures):
                try:
                    reports.append(future.result())
                except Exception as e:
                    print(f"Error for tests host: {futures[future]}: {e}")
                
        return reports
    
def read_hosts_from_file(filepath: str):
    try:
        with open(filepath, "r", encoding="utf-8") as input_file:
            hosts = []
            for line in input_file:
                stripped = line.strip()
                if len(stripped) > 0:
                    hosts.append(stripped)
            return hosts
    except Exception as e:
        print(f"Ошибка чтения file: {e}")
        return []
    
def write_reports(filepath: str, reports: list[HostTestReport]):
    try:
        with open(filepath, 'w+', encoding="utf-8") as output_file:
            for report in reports:
                output_file.write(report.to_string())
                
    except Exception as e:
        print(f"Ошибка записи file: {e}")
        
def print_reports(reports: list[HostTestReport]):
    for report in reports:
        print(report.to_string())
        
   