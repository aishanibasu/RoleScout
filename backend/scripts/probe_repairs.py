from probe_feeds import go
import concurrent.futures
query='query GetRoles($searchQueryInput: RoleSearchQueryInput!) { roleSearch(searchQueryInput: $searchQueryInput) { totalCount items { roleId jobTitle jobFunction locations { primary state country city } status division jobType { code description } } } }'
tasks={
'gs_fixed':('https://api-higher.gs.com/gateway/api/v1/graphql',{'operationName':'GetRoles','query':query,'variables':{'searchQueryInput':{'page':{'pageSize':100,'pageNumber':0},'sort':{'sortStrategy':'RELEVANCE','sortOrder':'DESC'},'filters':[],'experiences':['CAMPUS','EARLY_CAREER','PROFESSIONAL'],'searchTerm':''}}}),
'bny_first100':('https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_3001,limit=100,offset=0,sortBy=POSTING_DATES_DESC',None),
'bofa_late':('https://ghr.wd1.myworkdayjobs.com/wday/cxs/ghr/Lateral-US/jobs',{'appliedFacets':{},'limit':20,'offset':1980,'searchText':''}),
'jefferies_rss':('https://jefferies.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/candidate/jobboard/vacancy/2/feed',None),
}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for r in pool.map(go,tasks.items()):print(r,flush=True)
