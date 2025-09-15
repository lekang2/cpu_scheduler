import numpy as np

def generate_arrival_times(N, mean_iat, arrival_type):
    """ Generate inter-arrival times based on the specified pattern """
    if arrival_type == "constant":
        inter_arrival_times = [mean_iat] * N
    elif arrival_type == "poisson":
        inter_arrival_times = np.random.exponential(scale=mean_iat, size=N)
    elif arrival_type == "bursty":
        num_clusters = int(N/20)  # Number of burst clusters,each cluster has 20 requestes
        # Step 2: Randomly select cluster timestamps in the range [0, N * mean_iat]
        cluster_timestamps = np.sort(np.random.uniform(0, N * mean_iat, size=num_clusters))

        # Step 3: Assign each cluster's 20 requests to the same timestamp
        request_timestamps = np.repeat(cluster_timestamps, 20)  # Repeat each cluster timestamp 20 times

        # Step 4: Compute inter-arrival times
        inter_arrival_times = np.diff(request_timestamps, prepend=0)  # First cluster starts from 0
    elif arrival_type == "heavy_tail":
        mu = np.log(mean_iat)  # Mean of log(inter-arrival time)
        sigma = 1.0  # Standard deviation of log(inter-arrival time)
        inter_arrival_times = np.random.lognormal(mean=mu, sigma=sigma, size=N)
    else:
        raise ValueError("Unknown arrival type")

    return np.cumsum(inter_arrival_times).astype(int)

def generate_complexity(N, complexity_type):
    """ Generate job complexities based on different distributions """
    if complexity_type == "uniform":
        fib_values = np.random.randint(20, 36, size=N)  # Uniformly distributed
    elif complexity_type == "bimodal":
        fib_values = np.random.choice(
            np.concatenate([np.random.randint(20, 26, size=int(N*0.9)), np.random.randint(30, 36, size=int(N*0.1))]), 
            size=N
        )  # 90% small, 10% large
    elif complexity_type == "heavy_tail":
        fib_values_0 = np.random.lognormal(mean=np.log(28), sigma=1, size=N).astype(int)
        fib_values= np.array(fib_values_0)/8+20
        fib_values = np.clip(fib_values_0, 20, 35)

    elif complexity_type == "gaussian":
        fib_values = np.random.normal(loc=28, scale=5, size=N).astype(int)
        fib_values = np.clip(fib_values, 20, 35)  # Keep values in a valid range
    else:
        raise ValueError("Unknown complexity type")

    return fib_values

if __name__ == "__main__":
    N=400
    mean_iat=200
    
    arrival_type = "constant"  
    complexity_type = "heavy_tail"  
    # Generate request arrival times
    arrival_times = generate_arrival_times(N, mean_iat, arrival_type)

    # Generate function complexities (e.g., Fibonacci n values)
    complexities = generate_complexity(N, complexity_type)

    # Write to workload file
    output_file = "workload03.txt"
    with open(output_file, "w") as f:
        for i in range(N):
            job_name = f"fib{i+1}"
            function_executable = "fib.py"
            fib_n = complexities[i]
            start_time = arrival_times[i]
            job_id = i + 1  # Unique job ID

            f.write(f"{job_name} {function_executable} {fib_n} {start_time} {job_id}\n")
