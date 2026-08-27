// components/top-loader.tsx
import { useEffect, useState } from "react";
import { Progress } from "~/components/ui/progress";

export function TopLoader({ loading }: { loading: boolean }) {
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const [shouldRender, setShouldRender] = useState(false);

  useEffect(() => {
    let progressInterval: NodeJS.Timeout;
    let fadeTimer: NodeJS.Timeout;
    let unmountTimer: NodeJS.Timeout;

    if (loading) {
      setShouldRender(true);
      setVisible(true);
      setProgress(5); // Small initial jump for immediate feedback

      progressInterval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 90) return 90;
          // The closer to 90%, the smaller the steps (trickle)
          const remaining = 90 - prev;
          return prev + remaining * 0.1;
        });
      }, 300);
    } else {
      setProgress(100);
      // Briefly stay at 100% first, then fade out
      fadeTimer = setTimeout(() => {
        setVisible(false);
        // Wait until duration-500 (CSS) is over, only then unmount
        unmountTimer = setTimeout(() => {
          setShouldRender(false);
          setProgress(0);
        }, 500);
      }, 300);
    }

    return () => {
      clearInterval(progressInterval);
      clearTimeout(fadeTimer);
      clearTimeout(unmountTimer);
    };
  }, [loading]);

  if (!shouldRender) return null;

  return (
    <Progress
      value={progress}
      className={`fixed top-0 left-0 right-0 z-[100] h-1 rounded-none bg-transparent transition-all duration-700 ease-out ${
        !visible ? "opacity-0" : "opacity-100 shadow-[0_1px_8px_rgba(var(--primary),0.4)]"
      }`}
    />
  );
}
