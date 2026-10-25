/// Published catalog retailers. Replaced by server metadata when Api.stores lands.
const storeNames = <String, String>{
  'hm': 'H&M',
  'uniqlo': 'Uniqlo',
  'princesspolly': 'Princess Polly',
  'brandymelville': 'Brandy Melville',
  'edikted': 'Edikted',
  'trueclassic': 'True Classic',
  'kith': 'Kith',
  'stussy': 'Stüssy',
};
String storeName(String id) => storeNames[id] ?? id;
