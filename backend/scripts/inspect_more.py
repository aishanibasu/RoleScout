from probe_feeds import go,OUT
import concurrent.futures
TASKS={
'bny_detail':('https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?onlyData=true&finder=ById;Id=69526',None),
'morgan_feed':('https://www.morganstanley.com/web/career_services/webapp/service/careerservice/resultset.json?opportunity=ep&lang=en',None),
'morgan_student':('https://www.morganstanley.com/web/career_services/webapp/service/careerservice/resultset.json?opportunity=sg&lang=en',None),
'hft_jobs_script':('https://www.hft-jobs.com/assets/JobsPage-Dox9x8Lq.js',None),
 'twosigma_feed':('https://careers.twosigma.com/careers/OpenRoles/feed/?jobRecordsPerPage=100',None),
'jefferies_student':('https://jefferies.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/candidate/jobboard/vacancy/1/adv/',None),
}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(go,TASKS.items()):print(result,flush=True)
