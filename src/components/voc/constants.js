import ForumIcon from '@mui/icons-material/Forum';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import InsightsIcon from '@mui/icons-material/Insights';

export const DEFAULT_API_BASE = 'https://content-finder-backend-4ajpjhwlsq-ts.a.run.app';
export const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || DEFAULT_API_BASE;

export const STEPS = [
    {
        id: 'fetch-reddit',
        label: 'Fetch Reddit Posts',
        description: 'Gather posts from relevant subreddits',
        icon: ForumIcon,
    },
    {
        id: 'pre-score-posts',
        label: 'Pre-Score Posts',
        description: 'Fast AI batch scoring (title + snippet only)',
        icon: AutoAwesomeIcon,
    },
    {
        id: 'enrich-posts',
        label: 'Enrich High-Scorers',
        description: 'Fetch comments + deep AI analysis',
        icon: InsightsIcon,
    },
    {
        id: 'fetch-trends',
        label: 'Fetch Google Trends',
        description: 'Get trending search data',
        icon: TrendingUpIcon,
    },
    {
        id: 'generate-queries',
        label: 'Generate Queries',
        description: 'Create search queries from insights',
        icon: InsightsIcon,
    },
];

export const DEFAULT_SEGMENTS = ['SMB Leaders'];
