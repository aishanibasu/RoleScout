import concurrent.futures,json
from probe_sources import probe,OUT
PAGES={
'apollo_jobs':'https://athene.wd5.myworkdayjobs.com/Apollo_Careers',
'bofa_jobs':'https://ghr.wd1.myworkdayjobs.com/lateral-us',
'morgan_jobs':'https://www.morganstanley.com/careers/career-opportunities-search',
'jpmorgan_jobs':'https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/requisitions',
'bny_jobs':'https://eofe.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/BNY-Careers/jobs',
'jefferies_jobs':'https://careers.jefferies.com/',
'ubs_jobs':'https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5012&PageType=searchResults&SearchType=linkquery&LinkID=15231',
'rbc_jobs':'https://jobs.rbc.com/ca/en/search-results',
'gs_jobs':'https://higher.gs.com/results',
'twosigma_jobs':'https://careers.twosigma.com/',
'sig_jobs':'https://careers.sig.com/jobs',
'hft_script':'https://www.hft-jobs.com/assets/index-DZGjCrgg.js',
}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 results=list(pool.map(probe,PAGES.items()))
(OUT/'portals.json').write_text(json.dumps(results,indent=2))
for r in results:print(json.dumps(r),flush=True)
