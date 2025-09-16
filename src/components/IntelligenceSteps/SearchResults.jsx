import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  Alert,
  Paper,
  Stack,
  Chip,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
  Link
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Search as SearchIcon,
  Link as LinkIcon,
  Analytics as AnalyticsIcon,
  CheckCircle as CheckCircleIcon
} from '@mui/icons-material';
import { CustomColors, FontWeight } from '../../../theme';

const SearchResults = ({ sessionId, onSearchComplete }) => {
  const [sessionData, setSessionData] = useState(null);
  const [searching, setSearching] = useState(false);
  const [sources, setSources] = useState([]);
  const [error, setError] = useState('');
  const [groupedSources, setGroupedSources] = useState({});

  useEffect(() => {
    if (sessionId) {
      loadSession();
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionData?.searchResults) {
      processSearchResults();
    }
  }, [sessionData]);

  const loadSession = async () => {
    try {
      const response = await fetch(`https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/intelligence/sessions/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setSessionData(data);

        if (data.status === 'search_complete' && onSearchComplete) {
          onSearchComplete();
        }
      }
    } catch (error) {
      console.error('Failed to load session:', error);
      setError('Failed to load session data');
    }
  };

  const processSearchResults = () => {
    const allSources = [];
    const grouped = {};

    sessionData.searchResults?.forEach((result) => {
      result.sources?.forEach((source) => {
        allSources.push({
          ...source,
          query: result.query
        });

        // Group by domain
        if (!grouped[source.domain]) {
          grouped[source.domain] = [];
        }
        grouped[source.domain].push({
          ...source,
          query: result.query
        });
      });
    });

    setSources(allSources);
    setGroupedSources(grouped);
  };

  const startSearch = async () => {
    setSearching(true);
    setError('');

    try {
      const response = await fetch(`https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/intelligence/sessions/${sessionId}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Search failed');
      }

      const result = await response.json();

      // Reload session to get updated results
      await loadSession();

    } catch (error) {
      setError(error.message);
    } finally {
      setSearching(false);
    }
  };

  const handleSourceToggle = (sourceId, selected) => {
    setSources(prev => prev.map(s =>
        s.id === sourceId ? { ...s, selected } : s
    ));

    // Update grouped sources as well
    setGroupedSources(prev => {
      const updated = { ...prev };
      Object.keys(updated).forEach(domain => {
        updated[domain] = updated[domain].map(s =>
            s.id === sourceId ? { ...s, selected } : s
        );
      });
      return updated;
    });
  };

  const saveSourceChanges = async () => {
    try {
      const sourceUpdates = sources.map(s => ({
        id: s.id,
        selected: s.selected
      }));

      const response = await fetch(`https://content-finder-backend-4ajpjhwlsq-ts.a.run.app/api/intelligence/sessions/${sessionId}/sources`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sources: sourceUpdates })
      });

      if (!response.ok) {
        throw new Error('Failed to save source selections');
      }

      if (onSearchComplete) {
        onSearchComplete();
      }
    } catch (error) {
      setError(error.message);
    }
  };

  const selectedCount = sources.filter(s => s.selected).length;
  const totalSources = sources.length;
  const selectedQueries = sessionData?.queries?.filter(q => q.selected).length || 0;

  // Show search phase if no results yet
  if (!sessionData?.searchResults?.length) {
    return (
        <Box>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
            <Box>
              <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                Phase 2: Search Queries
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Search {selectedQueries} selected queries for relevant content
              </Typography>
            </Box>
            <Chip
                icon={<SearchIcon />}
                label={`${selectedQueries} queries ready`}
                color="primary"
                variant="outlined"
            />
          </Box>

          {error && (
              <Alert severity="error" sx={{ mb: 3 }}>
                {error}
              </Alert>
          )}

          <Paper elevation={0} sx={{ p: 3, textAlign: 'center', bgcolor: CustomColors.AliceBlue }}>
            <SearchIcon sx={{ fontSize: 48, color: CustomColors.DeepSkyBlue, mb: 2 }} />
            <Typography variant="h6" mb={1}>
              Ready to Search
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              Click below to search {selectedQueries} queries and find relevant sources
            </Typography>

            <Button
                variant="contained"
                color="primary"
                onClick={startSearch}
                disabled={searching}
                startIcon={searching ? <CircularProgress size={16} /> : <SearchIcon />}
                size="large"
            >
              {searching ? 'Searching...' : 'Start Search'}
            </Button>

            {searching && (
                <Box mt={2}>
                  <LinearProgress sx={{ borderRadius: 1 }} />
                  <Typography variant="caption" color="text.secondary" mt={1} display="block">
                    Searching across multiple sources...
                  </Typography>
                </Box>
            )}
          </Paper>
        </Box>
    );
  }

  // Show results phase
  return (
      <Box>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Box>
            <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
              Phase 2: Search Results
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Review and select sources for content analysis
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Chip
                icon={<CheckCircleIcon />}
                label={`${selectedCount} of ${totalSources} selected`}
                color={selectedCount > 0 ? "success" : "default"}
                variant="outlined"
            />
            <Chip
                label={`${Object.keys(groupedSources).length} domains`}
                variant="outlined"
            />
          </Stack>
        </Box>

        {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
        )}

        {/* Search Summary */}
        <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: CustomColors.AliceBlue }}>
          <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
            Search Summary
          </Typography>
          <Stack direction="row" spacing={3}>
            <Box>
              <Typography variant="h6" color="primary">
                {sessionData.stats?.queries_generated || 0}
              </Typography>
              <Typography variant="caption">Queries Searched</Typography>
            </Box>
            <Box>
              <Typography variant="h6" color="success.main">
                {totalSources}
              </Typography>
              <Typography variant="caption">Sources Found</Typography>
            </Box>
            <Box>
              <Typography variant="h6" color="secondary.main">
                {Object.keys(groupedSources).length}
              </Typography>
              <Typography variant="caption">Unique Domains</Typography>
            </Box>
          </Stack>
        </Paper>

        {/* Sources by Domain */}
        <Stack spacing={2} mb={3}>
          {Object.entries(groupedSources).map(([domain, domainSources]) => (
              <Accordion key={domain} defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
                    <Typography variant="subtitle1" fontWeight={FontWeight.Medium}>
                      {domain}
                    </Typography>
                    <Chip
                        size="small"
                        label={`${domainSources.length} sources`}
                        sx={{ mr: 2 }}
                    />
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={1}>
                    {domainSources.map((source) => (
                        <Card key={source.id} variant="outlined" sx={{ borderColor: source.selected ? CustomColors.SecretGarden : CustomColors.UIGrey300 }}>
                          <CardContent sx={{ py: 2 }}>
                            <Box display="flex" alignItems="flex-start" gap={2}>
                              <Checkbox
                                  checked={source.selected}
                                  onChange={(e) => handleSourceToggle(source.id, e.target.checked)}
                                  color="primary"
                              />
                              <Box flex={1}>
                                <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={0.5}>
                                  {source.title || 'Untitled'}
                                </Typography>
                                <Link
                                    href={source.url}
                                    target="_blank"
                                    variant="caption"
                                    sx={{ color: CustomColors.DeepSkyBlue, display: 'block', mb: 1 }}
                                >
                                  {source.url}
                                </Link>
                                <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.875rem' }}>
                                  {source.snippet}
                                </Typography>
                                <Typography variant="caption" color="text.secondary" display="block" mt={1}>
                                  From query: "{source.query}"
                                </Typography>
                              </Box>
                            </Box>
                          </CardContent>
                        </Card>
                    ))}
                  </Stack>
                </AccordionDetails>
              </Accordion>
          ))}
        </Stack>

        <Divider sx={{ my: 3 }} />

        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="body2" color="text.secondary">
            Select sources to analyze for content themes
          </Typography>

          <Button
              variant="contained"
              color="primary"
              onClick={saveSourceChanges}
              disabled={selectedCount === 0}
              startIcon={<AnalyticsIcon />}
          >
            Proceed with {selectedCount} Sources
          </Button>
        </Box>
      </Box>
  );
};

export default SearchResults;