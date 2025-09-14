// Add after the handleProcessSelected function
const handleCuratedTermClick = (term) => {
    setSearchQuery(term);
};

// Updated renderSearchResults function
const renderSearchResults = () => {
    if (!results?.steps?.search?.results) return null;

    const searchResults = results.steps.search.results;

    return (
        <Card sx={{ mb: 2 }}>
            <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">
                        <SearchIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                        Search Results ({searchResults.length} found)
                    </Typography>
                    <Box>
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={selectedUrls.size === searchResults.length && searchResults.length > 0}
                                    indeterminate={selectedUrls.size > 0 && selectedUrls.size < searchResults.length}
                                    onChange={(e) => handleSelectAll(e.target.checked)}
                                />
                            }
                            label="Select All"
                        />
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={handleProcessSelected}
                            disabled={selectedUrls.size === 0 || isProcessingSelected}
                            sx={{ ml: 2 }}
                        >
                            {isProcessingSelected ? (
                                <CircularProgress size={20} color="inherit" />
                            ) : (
                                `Process Selected (${selectedUrls.size})`
                            )}
                        </Button>
                    </Box>
                </Box>
                
                {searchResults.map((result, index) => (
                    <Paper 
                        key={index} 
                        elevation={0} 
                        sx={{ 
                            p: 2, 
                            mb: 1, 
                            border: `1px solid ${selectedUrls.has(result.url) ? CustomColors.DeepSkyBlue : CustomColors.UIGrey300}`,
                            borderRadius: 2,
                            backgroundColor: selectedUrls.has(result.url) ? CustomColors.AliceBlue : 'white'
                        }}
                    >
                        <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                            <Checkbox
                                checked={selectedUrls.has(result.url)}
                                onChange={(e) => handleUrlSelection(result.url, e.target.checked)}
                                sx={{ mt: 0, pt: 0 }}
                            />
                            <Box sx={{ flex: 1, ml: 1 }}>
                                <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                                    {result.title || `Search Result ${index + 1}`}
                                </Typography>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    {result.description || 'No description available'}
                                </Typography>
                                <Typography 
                                    variant="caption" 
                                    sx={{ 
                                        color: CustomColors.DeepSkyBlue,
                                        textDecoration: 'underline',
                                        cursor: 'pointer'
                                    }}
                                    onClick={() => window.open(result.url, '_blank')}
                                >
                                    <LinkIcon sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                                    {result.url}
                                </Typography>
                            </Box>
                        </Box>
                    </Paper>
                ))}
            </CardContent>
        </Card>
    );
};