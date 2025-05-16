"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";

import { useAuth } from "@/providers/AuthProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [emailSubmitted, setEmailSubmitted] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  const handleEmailSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email) {
      setError("Please enter your email address.");
      return;
    }
    if (!/\S+@\S+\.\S+/.test(email)) {
      setError("Please enter a valid email address.");
      return;
    }
    setEmailSubmitted(true);
  };

  const handleRegisterSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setLoading(true);
    try {
      await register({ email, password });
      setSuccess("Registration successful! Redirecting to login...");
      setTimeout(() => router.push("/login"), 2000);
    } catch (err: any) {
      let message = "Failed to register. Please try again.";
      if (err.response?.data?.detail) {
        message = err.response.data.detail;
      } else if (err.message) {
        message = err.message;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = (provider: string) => {
    console.log(`TODO: Implement ${provider} OAuth`);
    setLoading(true);
    setError(`OAuth with ${provider} is not yet implemented.`);
    setTimeout(() => setLoading(false), 1500);
  };

  const passwordVariants = {
    hidden: { opacity: 0, height: 0, marginTop: 0, marginBottom: 0 },
    visible: {
      opacity: 1,
      height: "auto",
      marginTop: "1rem",
      marginBottom: "1rem",
    },
  };

  return (
    <div className="bg-background flex min-h-screen items-center justify-center">
      <Card className="w-full max-w-md border shadow-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">Create an Account</CardTitle>
          <CardDescription>
            {emailSubmitted
              ? "Set your password to continue."
              : "Enter your email to get started."}
          </CardDescription>
        </CardHeader>
        <form
          onSubmit={emailSubmitted ? handleRegisterSubmit : handleEmailSubmit}
        >
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                aria-describedby="email-error"
              />
              {error && !emailSubmitted && (
                <p id="email-error" className="pt-1 text-sm text-red-600">
                  {error}
                </p>
              )}
            </div>

            <AnimatePresence>
              {emailSubmitted && (
                <motion.div
                  key="password-section"
                  variants={passwordVariants}
                  initial="hidden"
                  animate="visible"
                  exit="hidden"
                  transition={{ duration: 0.3, ease: "easeInOut" }}
                  className="space-y-4 overflow-hidden"
                >
                  <div className="space-y-2">
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      type="password"
                      required
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      disabled={loading}
                      aria-describedby="password-error"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="confirmPassword">Confirm Password</Label>
                    <Input
                      id="confirmPassword"
                      type="password"
                      required
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      disabled={loading}
                      aria-describedby="password-error"
                    />
                  </div>
                  {error && emailSubmitted && (
                    <p id="password-error" className="text-sm text-red-600">
                      {error}
                    </p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            {success && <p className="text-sm text-green-600">{success}</p>}

            {!emailSubmitted ? (
              <Button
                type="submit"
                className="w-full"
                disabled={loading || !email}
              >
                Continue
              </Button>
            ) : (
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Creating Account..." : "Create Account"}
              </Button>
            )}

            <div className="relative my-4">
              <Separator />
              <span className="bg-card text-muted-foreground absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 px-2 text-xs">
                OR CONTINUE WITH
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Button
                variant="outline"
                type="button"
                onClick={() => handleOAuth("Google")}
                disabled={loading}
                className="flex items-center justify-center"
              >
                <svg
                  role="img"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                  className="mr-2 h-4 w-4 fill-current"
                >
                  <title>Google</title>
                  <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.85 3.18-1.73 4.1-1.02 1.08-2.58 1.69-4.68 1.69-3.86 0-7-3.14-7-7s3.14-7 7-7c1.99 0 3.63.72 4.96 1.96l2.6-2.6C18.06 2.56 15.51 1.5 12.48 1.5c-6.18 0-11.23 4.99-11.23 11.17s5.05 11.17 11.23 11.17c3.1 0 5.56-1.03 7.41-2.86 1.96-1.92 2.9-4.75 2.9-8.14 0-.73-.07-1.47-.19-2.18h-10z" />
                </svg>
                Google
              </Button>
              <Button
                variant="outline"
                type="button"
                onClick={() => handleOAuth("GitHub")}
                disabled={loading}
                className="flex items-center justify-center"
              >
                <svg
                  role="img"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                  className="mr-2 h-4 w-4 fill-current"
                >
                  <title>GitHub</title>
                  <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
                </svg>
                GitHub
              </Button>
            </div>
          </CardContent>
          <CardFooter className="flex flex-col items-center space-y-2 pt-4">
            <p className="text-muted-foreground text-center text-sm">
              Already have an account?{" "}
              <Link
                href="/login"
                className="text-primary hover:text-primary/90 font-medium underline underline-offset-4"
              >
                Sign In
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
