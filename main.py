import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import sys
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
        self.success = 0
        self.failed = 0
        self.errors = 0
        self.min = float('inf')
        self.max = 0.0
        
        times_list = []
        for response in response_list:
            if response is None:
                self.errors += 1
                continue
            
            elapsed_ms = response.elapsed.total_seconds() * 1000
            
            if response.status_code == 200:
                self.success += 1
                times_list.append(elapsed_ms)
                if elapsed_ms < self.min:
                    self.min = elapsed_ms
                if elapsed_ms > self.max:
                    self.max = elapsed_ms
                    
            elif 400 <= response.status_code < 600:
                self.failed += 1
            else:
                self.errors += 1
                
        if len(times_list) > 0:
            self.avg = sum(times_list) / len(times_list)
            if self.min == float('inf'):
                self.min = 0.0
        else:
            self.avg = 0.0
            self.min = 0.0
        
    def to_string(self):
        return f"Host:    {self.host}\nSuccess: {self.success}\nFailed:  {self.failed}\nErrors:  {self.errors}\nMin:     {self.min:.2f} ms\nMax:     {self.max:.2f} ms\nAvg:     {self.avg:.2f} ms\n"
    
    
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
    
    def __init__(self):
        self.bench = HostHttpBench()
    
    def validate_url(self, url: str) -> bool:
        return bool(self.urls.match(url))
    
    def test_host(self, host: str, timeout: float = 10.0, count: int = 1) -> HostTestReport:
        if self.validate_url(host):
            responses = self.bench.get_response_list(url = host, timeout = timeout, count = count)
            return HostTestReport(host = host, response_list = responses)
        else:
            raise Exception(f'Невалидный URL: {host}')
        
    def test_hosts(self, hosts: list[str], timeout: float = 10.0, count: int = 1):
        reports: list[HostTestReport] = []
        try:
            for host in hosts:
                reports.append(self.test_host(host, timeout=timeout, count=count))
        except Exception as e:
            print(f'Ошибка: {e}')
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
                    host = futures.get(future, "неизвестный хост")
                    print(f"Ошибка для тестирования хоста: {host}: {e}")
                
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
                output_file.write("-" * 40 + "\n")
                
    except Exception as e:
        print(f"Ошибка записи file: {e}")
        
def print_reports(reports: list[HostTestReport]):
    for report in reports:
        print(report.to_string())
        print("-" * 40)
        
    
def main():
    parser = argparse.ArgumentParser(description='HTTP Host Bench')
    group = parser.add_mutually_exclusive_group()
    parser.add_argument('-T', '--timeout', type=float, default=10.0, help='Таймаут в секундах')
    group.add_argument('-F', '--file', type=str, help='Файл с хостами')
    group.add_argument('-H', '--hosts', type=str, help='Хосты через запятую')
    parser.add_argument('-O', '--output', type=str, help='Файл для вывода результатов')
    parser.add_argument('-C', '--count', type=int, default=1, help='Количество запросов на хост')
    parser.add_argument('-P', '--parallel', type=int, default=1, help='Количество потоков для параллельных запросов')
    args = parser.parse_args()
    
    if args.count  < 1:
        print('Количество запросов на хост должно быть больше 0')
        sys.exit(1)
        
    host_test = HttpHostTest()
    if args.hosts:
        hosts = [host.strip() for host in args.hosts.split(',')]
    else:
        hosts = read_hosts_from_file(args.file)
        
    if len(hosts) == 0:
        print('Нет хостов для тестирования')
        sys.exit(1)
    
    if args.parallel is not None and args.parallel > 1:
        reports = host_test.test_hosts_parallel(hosts, args.timeout, args.count, args.parallel)
    else:
        reports = host_test.test_hosts(hosts, args.timeout, args.count)
        
    if args.output is not None:
        write_reports(args.output, reports)
    else:
        print_reports(reports)
        

if __name__ == "__main__":
    main()