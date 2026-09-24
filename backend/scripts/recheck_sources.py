from probe_sources import probe
from probe_feeds import go
import concurrent.futures,json
pages={
'citadel_retry':'https://www.citadel.com/careers/open-opportunities/',
'jpmorgan_retry':'https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/requisitions',
'bam_retry':'https://www.bamfunds.com/careers',
'hudson_retry':'https://www.hudsonbaycapital.com/careers',
}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(probe,pages.items()):print(json.dumps(result),flush=True)
print(go(('bny_499',('https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_3001,limit=499,offset=0,sortBy=POSTING_DATES_DESC',None))),flush=True)
