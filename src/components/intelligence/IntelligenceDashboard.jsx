import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  LinearProgress,
  Alert,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Stack,
  Checkbox,
  FormControlLabel,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  TrendingUp as TrendingUpIcon,
  Psychology as PsychologyIcon,
  Search as SearchIcon,
  Link as LinkIcon,
  Assignment as AssignmentIcon,
  History as HistoryIcon,
  Edit as EditIcon
} from '@mui/icons-material';
import { CustomColors, FontWeight } from '../../theme';

const IntelligenceDashboard = () => {
  const [config, setConfig] = useState(null);
  const [sessions, setSessions] = useState({});
  const [activeSessions, setActiveSessions] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sessionDialogOpen, setSessionDialogOpen] = useState(false);
  const [selectedSegment, setSelectedSegment] = useState(null);

  useEffect(() => {
    loadIntelligenceConfig();
  }, []);

  const loadIntelligenceConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:5000/api/intelligence/config');
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      } else {
        setError('Failed to load intelligence configuration');
      }
    } catch (error) {
      console.error('Failed to load config:', error);
      setError('Failed to connect to intelligence API');
    } finally {
      setLoading(false);
    }
  };

  const createNewSession = async (segmentName) => {
    const segment = config?.monthly_run?.segments?.find(s => s.name === segmentName);
    if (!segment) return;

    setActiveSessions(prev => ({ ...prev, [segmentName]: 'generating' }));
    setError('');

    try {
      console.log(`🚀 Creating new session for: ${segmentName}`);

      const response = await fetch('http://localhost:5000/api/intelligence/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment_name: segmentName,
          mission: segment.research_focus
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const result = await response.json();
      
      // Store the session data
      setSessions(prev => ({
        ...prev,
        [segmentName]: {
          ...result.session,
          sessionId: result.session_id
        }
      }));

      setActiveSessions(prev => ({ ...prev, [segmentName]: result.session.status }));

      console.log(`✅ Session created for: ${segmentName} (ID: ${result.session_id})`);

    } catch (error) {
      console.error(`Failed to create session for ${segmentName}:`, error);
      setError(`Failed to create session for ${segmentName}: ${error.message}`);
      setActiveSessions(prev => ({ ...prev, [segmentName]: null }));
    }
  };

  const loadSession = async (sessionId, segmentName) => {
    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}`);
      if (response.ok) {
        const sessionData = await response.json();
        setSessions(prev => ({ ...prev, [segmentName]: sessionData }));
        setActiveSessions(prev => ({ ...prev, [segmentName]: sessionData.status }));
      }
    } catch (error) {
      console.error(`Failed to load session ${sessionId}:`, error);
    }
  };

  const updateQuerySelection = async (sessionId, segmentName, queryUpdates) => {
    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}/queries`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query_updates: queryUpdates })
      });

      if (response.ok) {
        // Reload session to get updated data
        await loadSession(sessionId, segmentName);
      }
    } catch (error) {
      console.error('Failed to update query selection:', error);
      setError('Failed to update query selection');
    }
  };

  const searchSelectedQueries = async (sessionId, segmentName) => {
    setActiveSessions(prev => ({ ...prev, [segmentName]: 'searching' }));

    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      // Reload session to get search results
      await loadSession(sessionId, segmentName);

    } catch (error) {
      console.error('Failed to search queries:', error);
      setError(`Failed to search queries: ${error.message}`);
      setActiveSessions(prev => ({ ...prev, [segmentName]: 'queries_ready' }));
    }
  };

  const updateSourceSelection = async (sessionId, segmentName, sourceUpdates) => {
    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}/sources`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_updates: sourceUpdates })
      });

      if (response.ok) {
        await loadSession(sessionId, segmentName);
      }
    } catch (error) {
      console.error('Failed to update source selection:', error);
      setError('Failed to update source selection');
    }
  };

  const analyzeSelectedSources = async (sessionId, segmentName) => {
    setActiveSessions(prev => ({ ...prev, [segmentName]: 'analyzing' }));

    try {
      const response = await fetch(`http://localhost:5000/api/intelligence/sessions/${sessionId}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      // Reload session to get analysis results
      await loadSession(sessionId, segmentName);

    } catch (error) {
      console.error('Failed to analyze sources:', error);
      setError(`Failed to analyze sources: ${error.message}`);
      setActiveSessions(prev => ({ ...prev, [segmentName]: 'search_complete' }));
    }
  };

  const showSessionHistory = (segmentName) => {
    setSelectedSegment(segmentName);
    setSessionDialogOpen(true);
  };

  const renderSessionCard = (segment) => {
    const session = sessions[segment.name];
    const status = activeSessions[segment.name];
    const hasSession = !!session;

    return (
      <Grid item xs={12} md={6} key={segment.name}>
        <Card sx={{
          height: '100%',
          border: `2px solid ${
            status === 'complete' ? CustomColors.SecretGarden :
            status ? CustomColors.DeepSkyBlue :
            CustomColors.UIGrey300
          }`
        }}>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6" fontWeight={FontWeight.SemiBold}>
                {segment.name}
              </Typography>
              <Stack direction="row" spacing={1}>
                <Chip
                  label="Session-Based"
                  size="small"
                  variant="outlined"
                  sx={{
                    borderColor: CustomColors.DeepSkyBlue,
                    color: CustomColors.DeepSkyBlue
                  }}
                />
                <IconButton size="small" onClick={() => showSessionHistory(segment.name)}>
                  <HistoryIcon />
                </IconButton>
              </Stack>
            </Box>

            <Typography variant="body2" color="text.secondary" mb={2}>
              {segment.description}
            </Typography>

            {/* Session Status & Progress */}
            {hasSession && (
              <Paper elevation={0} sx={{ p: 2, mb: 2, bgcolor: CustomColors.AliceBlue }}>
                <Typography variant="subtitle2" mb={1} fontWeight={FontWeight.Medium}>
                  Session Progress:
                </Typography>
                <Box display="flex" alignItems="center" gap={2} mb={1}>
                  <Typography variant="body2" color="primary" fontWeight={FontWeight.Medium}>
                    {getStatusDisplay(status)}
                  </Typography>
                  {isStatusActive(status) && <CircularProgress size={16} />}
                </Box>
                
                {/* Progress Stats */}
                <Stack direction="row" spacing={2}>
                  <Box>
                    <Typography variant="h6" color="primary" fontWeight={FontWeight.Bold}>
                      {session.stats?.queries_generated || 0}
                    </Typography>
                    <Typography variant="caption">Queries</Typography>
                  </Box>
                  <Box>
                    <Typography variant="h6" color="success.main" fontWeight={FontWeight.Bold}>
                      {session.stats?.sources_found || 0}
                    </Typography>
                    <Typography variant="caption">Sources</Typography>
                  </Box>
                  <Box>
                    <Typography variant="h6" color="secondary.main" fontWeight={FontWeight.Bold}>
                      {session.stats?.themes_generated || 0}
                    </Typography>
                    <Typography variant="caption">Themes</Typography>
                  </Box>
                </Stack>
              </Paper>
            )}

            {/* Session Workflow Steps */}
            {hasSession && renderSessionWorkflow(session, segment.name, status)}

            {/* Action Buttons */}
            <Divider sx={{ my: 2 }} />
            <Box display="flex" justifyContent="space-between" alignItems="center">
              {!hasSession ? (
                <Button
                  variant="contained"
                  color="primary"
                  onClick={() => createNewSession(segment.name)}
                  disabled={loading}
                  startIcon={<PsychologyIcon />}
                >
                  Start New Session
                </Button>
              ) : (
                renderActionButton(session, segment.name, status)
              )}

              {hasSession && session.updatedAt && (
                <Typography variant="caption" color="text.secondary">
                  Updated: {new Date(session.updatedAt.seconds * 1000).toLocaleString()}
                </Typography>
              )}
            </Box>
          </CardContent>
        </Card>
      </Grid>
    );
  };

  const renderSessionWorkflow = (session, segmentName, status) => {
    const { queries = [], searchResults = [], themes = [] } = session;

    return (
      <Box mb={2}>
        {/* Step 1: Query Generation & Selection */}
        {queries.length > 0 && (
          <Accordion defaultExpanded={status === 'queries_ready'}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2" fontWeight={FontWeight.SemiBold}>
                <SearchIcon sx={{ mr: 1, verticalAlign: 'middle', fontSize: 16 }} />
                Generated Queries ({queries.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <List dense>
                {queries.map((query, idx) => (
                  <ListItem key={query.id} sx={{ px: 0 }}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={query.selected}
                          onChange={(e) => {
                            const updates = [{
                              id: query.id,
                              selected: e.target.checked
                            }];
                            updateQuerySelection(session.sessionId, segmentName, updates);
                          }}
                          disabled={status !== 'queries_ready'}
                        />
                      }
                      label={
                        <Typography variant="body2">
                          {idx + 1}. {query.text}
                        </Typography>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
        )}

        {/* Step 2: Search Results & Source Selection */}
        {searchResults.length > 0 && (
          <Accordion defaultExpanded={status === 'search_complete'} sx={{ mt: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2" fontWeight={FontWeight.SemiBold}>
                <LinkIcon sx={{ mr: 1, verticalAlign: 'middle', fontSize: 16 }} />
                Search Results ({getTotalSources(searchResults)} sources)
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              {searchResults.map((result, idx) => (
                <Box key={idx} mb={2}>
                  <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
                    Query: {result.query}
                  </Typography>
                  <List dense>
                    {result.sources?.map((source) => (
                      <ListItem key={source.id} sx={{ px: 0 }}>
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={source.selected}
                              onChange={(e) => {
                                const updates = [{
                                  id: source.id,
                                  selected: e.target.checked
                                }];
                                updateSourceSelection(session.sessionId, segmentName, updates);
                              }}
                              disabled={status !== 'search_complete'}
                            />
                          }
                          label={
                            <Box>
                              <Typography variant="body2" fontWeight={FontWeight.Medium}>
                                {source.title}
                              </Typography>
                              <Typography 
                                variant="caption" 
                                sx={{ 
                                  cursor: 'pointer', 
                                  color: CustomColors.DeepSkyBlue,
                                  display: 'block'
                                }}
                                onClick={() => window.open(source.url, '_blank')}
                              >
                                {source.url}
                              </Typography>
                            </Box>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              ))}
            </AccordionDetails>
          </Accordion>
        )}

        {/* Step 3: Analysis Results */}
        {themes.length > 0 && (
          <Accordion defaultExpanded={status === 'complete'} sx={{ mt: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2" fontWeight={FontWeight.SemiBold}>
                <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle', fontSize: 16 }} />
                Content Themes ({themes.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              {themes.map((theme, idx) => (
                <Paper key={idx} elevation={0} sx={{ p: 2, mb: 2, bgcolor: CustomColors.UIGrey100 }}>
                  <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
                    {theme.theme}
                  </Typography>
                  <Typography variant="body2" mb={1}>
                    {theme.key_insight}
                  </Typography>
                  {theme.why_smbs_care && (
                    <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                      Why SMBs care: {theme.why_smbs_care}
                    </Typography>
                  )}
                  {theme.linkedin_angle && (
                    <Typography variant="caption" color="primary" display="block">
                      LinkedIn angle: {theme.linkedin_angle}
                    </Typography>
                  )}
                </Paper>
              ))}
            </AccordionDetails>
          </Accordion>
        )}
      </Box>
    );
  };

  const renderActionButton = (session, segmentName, status) => {
    switch (status) {
      case 'generating':
        return (
          <Button disabled startIcon={<CircularProgress size={16} />}>
            Generating Queries...
          </Button>
        );
      
      case 'queries_ready':
        const selectedQueries = session.queries?.filter(q => q.selected) || [];
        return (
          <Button
            variant="contained"
            color="primary"
            onClick={() => searchSelectedQueries(session.sessionId, segmentName)}
            disabled={selectedQueries.length === 0}
            startIcon={<SearchIcon />}
          >
            Search ({selectedQueries.length} queries)
          </Button>
        );
      
      case 'searching':
        return (
          <Button disabled startIcon={<CircularProgress size={16} />}>
            Searching...
          </Button>
        );
      
      case 'search_complete':
        const selectedSources = getSelectedSources(session.searchResults || []);
        return (
          <Button
            variant="contained"
            color="secondary"
            onClick={() => analyzeSelectedSources(session.sessionId, segmentName)}
            disabled={selectedSources.length === 0}
            startIcon={<PsychologyIcon />}
          >
            Analyze ({selectedSources.length} sources)
          </Button>
        );
      
      case 'analyzing':
        return (
          <Button disabled startIcon={<CircularProgress size={16} />}>
            Analyzing...
          </Button>
        );
      
      case 'complete':
        return (
          <Button
            variant="outlined"
            color="primary"
            onClick={() => createNewSession(segmentName)}
            startIcon={<PsychologyIcon />}
          >
            Start New Session
          </Button>
        );
      
      default:
        return (
          <Button
            variant="contained"
            color="primary"
            onClick={() => createNewSession(segmentName)}
            startIcon={<PsychologyIcon />}
          >
            Start Session
          </Button>
        );
    }
  };

  // Helper functions
  const getStatusDisplay = (status) => {
    const statusMap = {
      'generating': 'Generating Queries',
      'queries_ready': 'Ready to Search',
      'searching': 'Searching Sources',
      'search_complete': 'Ready to Analyze',
      'analyzing': 'Analyzing Content',
      'complete': 'Analysis Complete'
    };
    return statusMap[status] || 'Unknown';
  };

  const isStatusActive = (status) => {
    return ['generating', 'searching', 'analyzing'].includes(status);
  };

  const getTotalSources = (searchResults) => {
    return searchResults.reduce((total, result) => total + (result.sources?.length || 0), 0);
  };

  const getSelectedSources = (searchResults) => {
    const sources = [];
    searchResults.forEach(result => {
      result.sources?.forEach(source => {
        if (source.selected) sources.push(source);
      });
    });
    return sources;
  };

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h5" component="h1" fontWeight={FontWeight.Bold}>
            Intelligence Engine
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Session-based AI research with dynamic query generation and source analysis
          </Typography>
        </Box>
      </Box>

      {/* Global Loading */}
      {loading && <LinearProgress sx={{ mb: 3 }} />}

      {/* Global Error */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Configuration Info */}
      {config && (
        <Paper elevation={0} sx={{ p: 2, mb: 3, bgcolor: CustomColors.AliceBlue }}>
          <Typography variant="subtitle2" fontWeight={FontWeight.Medium} mb={1}>
            Session-Based Research Configuration
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • Multi-phase workflow: Generate → Search → Analyze
            • Persistent sessions with Firestore
            • Query and source selection controls
            • AI synthesis for LinkedIn content insights
            • Max {config.monthly_run?.scrape_top || 5} results per query
          </Typography>
        </Paper>
      )}

      {/* Segment Cards */}
      {config && (
        <Grid container spacing={3}>
          {config.monthly_run?.segments?.map(renderSessionCard)}
        </Grid>
      )}

      {/* Session History Dialog */}
      <Dialog 
        open={sessionDialogOpen} 
        onClose={() => setSessionDialogOpen(false)}
        maxWidth="md" 
        fullWidth
      >
        <DialogTitle>Session History - {selectedSegment}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            Session history functionality coming soon...
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSessionDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default IntelligenceDashboard;
