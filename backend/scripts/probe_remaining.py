from probe_feeds import go,OUT
import concurrent.futures,json,re
query='query GetRoles($searchQueryInput: RoleSearchQueryInput!) { roleSearch(searchQueryInput: $searchQueryInput) { totalCount items { roleId jobTitle jobFunction locations { primary state country city } status division jobType { code description } } } }'
TASKS={
'bny_page2':('https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_3001,limit=100,offset=100',None),
'gs_feed':('https://api-higher.gs.com/gateway/api/v1/graphql',{'operationName':'GetRoles','query':query,'variables':{'searchQueryInput':{'page':{'pageSize':100,'pageNumber':0},'sort':'RELEVANCE','filters':[],'experiences':['CAMPUS','EARLY_CAREER','PROFESSIONAL'],'searchTerm':''}}}),
 'twosigma_detail':('https://careers.twosigma.com/careers/JobDetail/New-York-New-York-United-States-AI-Research-Scientist-Campus-Full-Time/13671',None),
'jefferies_detail':('https://jefferies.tal.net/vx/lang-en-GB/mobile-0/appcentre-1/brand-4/candidate/so/pm/1/pl/2/opp/1935-2027-Investment-Banking-Analyst-Programme-London/en-GB',None),
}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(go,TASKS.items()):print(result,flush=True)
