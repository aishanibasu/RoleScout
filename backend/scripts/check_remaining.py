from probe_sources import probe
import concurrent.futures,json
pages={'citadel_check':'https://www.citadel.com/careers/open-opportunities/','jpm_check':'https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/requisitions','jpm_students':'https://www.jpmorganchase.com/careers/explore-opportunities/students-and-graduates','hudson_check':'https://www.hudsonbaycapital.com/careers'}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(probe,pages.items()):print(json.dumps(result),flush=True)
